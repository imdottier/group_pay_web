'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import { XMarkIcon, ArrowUpCircleIcon, ArrowDownCircleIcon, TrashIcon } from '@heroicons/react/24/outline';
import { toast } from 'sonner';

interface User {
  user_id: number;
  username: string;
  full_name: string;
  email: string;
  profile_image_url?: string;
}

type GroupRole = "owner" | "admin" | "member";

const roleHierarchy: Record<GroupRole, number> = {
  owner: 2,
  admin: 1,
  member: 0,
};

interface UserProfileModalProps {
  userId: number;
  groupId: string;
  currentUserId: number;
  currentUserRole: GroupRole | null;
  onClose: () => void;
      onActionCompleted: () => void;
}

const UserProfileModal: React.FC<UserProfileModalProps> = ({ userId, groupId, currentUserId, currentUserRole, onClose, onActionCompleted }) => {
  const [user, setUser] = useState<User | null>(null);
  const [userRole, setUserRole] = useState<GroupRole | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId || !groupId) return;

    const fetchUserData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [userRes, roleRes] = await Promise.all([
          api.get<User>(`/users/${userId}`),
          api.get<{ role: GroupRole }>(`/groups/${groupId}/members/${userId}/role`)
        ]);
        setUser(userRes.data);
        setUserRole(roleRes.data.role);
      } catch (err: any) {
        console.error("Failed to fetch user profile data:", err);
        setError(err.response?.data?.detail || "Could not load user profile. Please try again.");
        toast.error(err.response?.data?.detail || "Failed to load user profile.");
      }
      setIsLoading(false);
    };

    fetchUserData();
  }, [userId, groupId]);

  const handleRoleChange = async (newRole: GroupRole) => {
    if (!userRole) return;
    try {
      await api.put(`/groups/${groupId}/members/${userId}/role`, { role: newRole });
      toast.success(`Successfully updated ${user?.username}'s role to ${newRole}.`);
      onActionCompleted(); // This will close the modal and refresh the list
    } catch (err: any) {
      console.error('Failed to change role', err);
      toast.error(err.response?.data?.detail || 'Failed to change role.');
    }
  };

  const handleRemoveMember = async () => {
    try {
      await api.delete(`/groups/${groupId}/members/${userId}`);
      toast.success(`Successfully removed ${user?.username} from the group.`);
      onActionCompleted(); // This will close the modal and refresh the list
    } catch (err: any) {
      console.error('Failed to remove member', err);
      toast.error(err.response?.data?.detail || 'Failed to remove member.');
    }
  };
  
  const canManage = currentUserRole && userRole && roleHierarchy[currentUserRole] > roleHierarchy[userRole];

  const renderManagementButtons = () => {
    if (!canManage || !userRole) return null;

    const promoteTo = userRole === 'member' ? 'admin' : 'owner';

    return (
      <div className="flex items-center gap-2">
        <button
          onClick={() => handleRoleChange(promoteTo)}
          className="flex items-center justify-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
        >
          <ArrowUpCircleIcon className="h-5 w-5" />
          Promote to {capitalizeRole(promoteTo)}
        </button>

        {userRole === 'admin' && (
          <button
            onClick={() => handleRoleChange('member')}
            className="flex items-center justify-center gap-2 rounded-md bg-yellow-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-yellow-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-600"
          >
            <ArrowDownCircleIcon className="h-5 w-5" />
            Demote to Member
          </button>
        )}
        
        {userRole === 'member' && (
           <button
             onClick={handleRemoveMember}
             className="flex items-center justify-center gap-2 rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600"
           >
             <TrashIcon className="h-5 w-5" />
             Remove from Group
           </button>
        )}
      </div>
    );
  };


  const ProfileContent = () => {
    if (isLoading) return <div className="text-center p-8">Loading profile...</div>;
    if (error) return <div className="text-center p-8 text-red-600 bg-red-50 rounded-lg">{error}</div>;
    if (!user) return <div className="text-center p-8">User not found.</div>;

    const profileImageUrl = user.profile_image_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(user.full_name || user.username)}&background=random`;

    return (
      <>
        <div className="p-6">
            <div className="flex items-center space-x-4">
                <img
                src={profileImageUrl}
                alt={`${user.full_name || user.username}'s profile`}
                className="h-24 w-24 rounded-full object-cover border-4 border-gray-200"
                />
                <div>
                <h2 className="text-2xl font-bold text-gray-800">{user.full_name}</h2>
                <p className="text-md text-gray-500">@{user.username}</p>
                <span className="mt-2 inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
                    {capitalizeRole(userRole || '')}
                </span>
                </div>
            </div>
        </div>
      </>
    );
  };

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex justify-center items-center" onClick={onClose}>
      <div className="relative mx-auto p-0 border w-full max-w-lg shadow-lg rounded-md bg-white" onClick={e => e.stopPropagation()}>
        <div className="absolute top-0 right-0 pt-4 pr-4">
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <span className="sr-only">Close</span>
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        <ProfileContent />

        <div className="bg-gray-50 px-4 py-3 sm:px-6 flex justify-between items-center">
          <div>
            {userId !== currentUserId && renderManagementButtons()}
          </div>
          <button
            type="button"
            className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

const capitalizeRole = (role: string) => {
    if (!role) return '';
    return role.charAt(0).toUpperCase() + role.slice(1);
};


export default UserProfileModal; 