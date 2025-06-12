'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api'; // Assuming your api instance is here
import Link from 'next/link';
import GroupInvitationsModal from '@/components/groups/GroupInvitationsModal';

interface Group {
  group_id: number;
  group_name: string;
  // Add other group properties as needed
}

export default function AuthenticatedHomePage() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isInvitationsOpen, setIsInvitationsOpen] = useState(false);
  const router = useRouter();

  const fetchGroups = useCallback(async () => {
    try {
      const response = await api.get<Group[]>('/groups/');
      setGroups(response.data);
      setError(null);
    } catch (err: any) {
      console.error("Failed to fetch groups:", err);
      if (err.response && err.response.status === 401) {
        router.push('/login');
      } else {
        setError("Failed to load groups. Please try again later.");
      }
    }
    setIsLoading(false);
  }, [router]);

  useEffect(() => {
    setIsLoading(true);
    fetchGroups().finally(() => setIsLoading(false));
  }, [fetchGroups]);

  const handleInvitationAccepted = () => {
    fetchGroups(); // Refetch groups to show the newly joined one
    setIsInvitationsOpen(false); // Close the modal
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-t-2 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-10">
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  return (
    <>
      <div className="container mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-semibold text-gray-800">Your Groups</h1>
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setIsInvitationsOpen(true)}
              className="bg-teal-500 hover:bg-teal-600 text-white font-bold py-2 px-4 rounded-lg shadow-md transition duration-150 ease-in-out"
            >
              Invitations
            </button>
            {groups.length > 0 && (
              <Link href="/groups/create" passHref>
                <button className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded-lg shadow-md transition duration-150 ease-in-out">
                  Create New Group
                </button>
              </Link>
            )}
          </div>
        </div>

        {groups.length === 0 ? (
          <div className="text-center py-10">
            <p className="text-gray-600 text-lg mb-4">You are not part of any groups yet.</p>
            <Link href="/groups/create" passHref>
              <button className="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-6 rounded-lg shadow-md transition duration-150 ease-in-out">
                Create Your First Group
              </button>
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {groups.map((group) => (
              <Link key={group.group_id} href={`/groups/${group.group_id}?tab=members`} passHref>
                <div className="bg-white rounded-xl shadow-lg overflow-hidden hover:shadow-xl transition-shadow duration-300 ease-in-out cursor-pointer h-full flex flex-col">
                  <div className="p-6 flex-grow">
                    <h2 className="text-xl font-semibold text-gray-700 mb-2">{group.group_name}</h2>
                    {/* Placeholder for more group info e.g., number of members, last activity */}
                    <p className="text-sm text-gray-500">View details & expenses</p>
                  </div>
                  <div className="bg-gray-50 px-6 py-3">
                    <span className="text-indigo-600 hover:text-indigo-700 font-medium text-sm">Open Group</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
      <GroupInvitationsModal
        isOpen={isInvitationsOpen}
        onClose={() => setIsInvitationsOpen(false)}
        onInvitationAccepted={handleInvitationAccepted}
      />
    </>
  );
} 