'use client';

import { useEffect, useState, Fragment } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import api from '@/lib/api';
import GroupPageTabs, { GroupTab } from '@/components/GroupPageTabs';
import MembersContent from '@/components/group/MembersContent';
import PaymentsContent from '@/components/group/PaymentsContent';
import ActivityContent from '@/components/group/ActivityContent';
import { GroupBills } from '@/components/group/GroupBills';
import EditGroupModal from '@/components/group/EditGroupModal';
import { Dialog, Transition } from '@headlessui/react';
import { toast } from 'sonner';
import DashboardContent from '@/components/group/DashboardContent';
import { mutate } from 'swr';

interface User {
  user_id: number;
  username: string;
}

interface GroupDetails {
  group_id: number;
  group_name: string;
  description: string | null;
}

// Dummy component for Bills tab (if not yet implemented)
// const BillsContent = ({ groupId }: { groupId: string }) => (
//   <div className="bg-white shadow-sm p-6 rounded-lg">
//     <h2 className="text-xl font-semibold text-gray-700">Bills</h2>
//     <p className="text-gray-600 mt-2">Bill list for group {groupId} will be here.</p>
//   </div>
// );

export default function GroupDetailPage() {
  const params = useParams();
  const groupId = Array.isArray(params.groupId) ? params.groupId[0] : params.groupId;
  const router = useRouter();
  const searchParams = useSearchParams();

  const [group, setGroup] = useState<GroupDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<GroupTab>('members');
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isLoadingCurrentUser, setIsLoadingCurrentUser] = useState(true);
  const [currentUserError, setCurrentUserError] = useState<string | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isLeaveModalOpen, setIsLeaveModalOpen] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);

  useEffect(() => {
    const tab = searchParams.get('tab') as GroupTab;
    if (tab && ['dashboard', 'members', 'bills', 'payments', 'activity', 'settings'].includes(tab)) {
      setActiveTab(tab);
    } else {
      // Default to 'members' if no valid tab is found
      setActiveTab('members');
    }
  }, [searchParams]);

  useEffect(() => {
    if (groupId) {
      const fetchGroupDetails = async () => {
        setIsLoading(true);
        try {
          const response = await api.get<GroupDetails>(`/groups/${groupId}`);
          setGroup(response.data);
          setError(null);
        } catch (err) {
          console.error("Failed to fetch group details:", err);
          setError("Failed to load group details. Make sure the group exists and you are a member.");
        }
        setIsLoading(false);
      };
      fetchGroupDetails();
    }
  }, [groupId]);

  useEffect(() => {
    const fetchCurrentUser = async () => {
      setIsLoadingCurrentUser(true);
      try {
        const response = await api.get<User>('/users/me');
        setCurrentUser(response.data);
        setCurrentUserError(null);
      } catch (err) {
        console.error("Failed to fetch current user:", err);
        setCurrentUserError("Failed to load your user information.");
      }
      setIsLoadingCurrentUser(false);
    };
    fetchCurrentUser();
  }, []);

  if (!groupId) {
    return <div className="text-center py-10">No Group ID provided.</div>;
  }

  if (isLoading) {
    return <div className="text-center py-10">Loading group details...</div>;
  }

  if (isLoadingCurrentUser) {
    return <div className="text-center py-10">Loading user data...</div>;
  }

  if (error) {
    return <div className="text-center py-10 text-red-500">{error}</div>;
  }

  if (!group) {
    return <div className="text-center py-10">Group not found or you do not have access.</div>;
  }

  if (currentUserError) {
    return <div className="text-center py-10 text-red-500">{currentUserError}</div>;
  }

  if (!currentUser) {
    return <div className="text-center py-10">Could not load current user.</div>;
  }

  const handleTabChange = (tab: GroupTab) => {
    setActiveTab(tab);
    router.push(`/groups/${groupId}?tab=${tab}`, { scroll: false });
  };

  const handlePaymentCreated = () => {
    // When a payment is created from another tab, switch to the payments tab
    // and force a re-fetch of the payments data.
    const defaultPaymentsUrl = `/groups/${groupId}/payments?skip=0&limit=20&sort_by=created_at&sort_order=desc&filter_type=all`;
    mutate(defaultPaymentsUrl);
    handleTabChange('payments');
  }

  const handleGroupUpdated = (updatedGroupData: GroupDetails) => {
    setGroup(updatedGroupData);
  };

  const handleLeaveGroup = async () => {
    if (!currentUser) {
        toast.error("Could not verify user. Please refresh and try again.");
        return;
    }
    setIsLeaving(true);
    try {
      await api.delete(`/groups/${groupId}/leave`);
      toast.success("You have successfully left the group.");
      // Force a full page reload on navigation to ensure group list is fresh
      window.location.href = '/';
    } catch (err: any) {
      console.error("Failed to leave group:", err);
      toast.error(err.response?.data?.detail || "Failed to leave the group.");
      setIsLeaving(false);
      setIsEditModalOpen(false); // Close modal on error
    } 
  };

  return (
    <div className="w-full">
      {/* Group Header */}
      <div className="bg-white shadow-sm p-4 sm:p-6 mb-6 rounded-lg relative">
        <div className="absolute top-4 right-4 sm:top-6 sm:right-6 flex items-center space-x-2">
          <button 
            onClick={() => setIsEditModalOpen(true)}
            className="text-sm text-indigo-600 hover:text-indigo-800 border border-indigo-300 hover:border-indigo-500 px-3 py-1 rounded-md transition-colors duration-150 ease-in-out"
          >
            Edit Group Info
          </button>
          <button 
            onClick={() => setIsLeaveModalOpen(true)}
            className="text-sm text-red-600 hover:text-red-800 border border-red-300 hover:border-red-500 px-3 py-1 rounded-md transition-colors duration-150 ease-in-out"
          >
            Leave Group
          </button>
        </div>
        <div className="mb-4 pr-24">
            <Link href="/" passHref>
            <span className="text-sm text-indigo-600 hover:text-indigo-800 transition-colors duration-150 ease-in-out cursor-pointer">
                &larr; Back to All Groups
            </span>
            </Link>
        </div>
        <div className="pr-24">
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-800 mb-2">{group.group_name}</h1>
            {group.description && <p className="text-gray-600 text-sm sm:text-base">{group.description}</p>}
        </div>
      </div>

      <GroupPageTabs currentGroupId={groupId as string} activeTab={activeTab} onTabChange={handleTabChange} />

      {/* Tab Content Area */}
      <div className="mt-0">
        <div style={{ display: activeTab === 'dashboard' ? 'block' : 'none' }}>
            <DashboardContent groupId={groupId as string} />
        </div>
        <div style={{ display: activeTab === 'members' ? 'block' : 'none' }}>
            <MembersContent groupId={groupId as string} currentUser={currentUser} />
        </div>
        <div style={{ display: activeTab === 'bills' ? 'block' : 'none' }}>
            <GroupBills groupId={groupId as string} currentUser={currentUser} onPaymentCreated={handlePaymentCreated} />
        </div>
        <div style={{ display: activeTab === 'payments' ? 'block' : 'none' }}>
            <PaymentsContent groupId={groupId as string} />
        </div>
        <div style={{ display: activeTab === 'activity' ? 'block' : 'none' }}>
            <ActivityContent groupId={groupId as string} />
        </div>
      </div>

      {group && (
        <EditGroupModal
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          group={group}
          onGroupUpdated={handleGroupUpdated}
        />
      )}

      {/* Leave Group Confirmation Modal */}
      {group && (
      <Transition appear show={isLeaveModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-10" onClose={() => setIsLeaveModalOpen(false)}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/30 backdrop-blur-sm" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4 text-center">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
                  <Dialog.Title as="h3" className="text-lg font-medium leading-6 text-gray-900">
                    Leave Group
                  </Dialog.Title>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500">
                      Are you sure you want to leave &quot;{group.group_name}&quot;? This action cannot be undone.
                    </p>
                  </div>

                  <div className="mt-4 flex justify-end space-x-2">
                    <button
                      type="button"
                      className="inline-flex justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
                      onClick={() => setIsLeaveModalOpen(false)}
                      disabled={isLeaving}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="inline-flex justify-center rounded-md border border-transparent bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 disabled:bg-red-400"
                      onClick={handleLeaveGroup}
                      disabled={isLeaving}
                    >
                      {isLeaving ? 'Leaving...' : 'Leave'}
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
      )}
    </div>
  );
} 