'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import { PlusCircleIcon, UserIcon } from '@heroicons/react/24/outline';
import InviteMemberModal from './InviteMemberModal';
import UserProfileModal from '@/components/user/UserProfileModal';
import { formatCurrency } from '@/lib/utils';
import { User } from '@/types';

// --- Interfaces ---
type GroupRole = "owner" | "admin" | "member";

interface GroupMember {
  group_id: number;
  role: GroupRole;
  user: User;
  joined_at: string;
}

interface UserNetBalance {
  user_id: number;
  username: string;
  net_amount: number;
}

interface GroupBalanceSummary {
  group_id: number;
  balances: UserNetBalance[];
}

interface MemberDisplayInfo extends UserNetBalance {
  role: GroupRole | string;
  joined_at?: string;
  profile_image_url?: string;
}

interface PendingInvitation {
    invitation_id: number;
    group_id: number;
    inviter: User;
    invitee: User;
    status: 'pending';
    created_at: string;
}

interface MembersContentProps {
  groupId: string;
  currentUser: { user_id: number };
}

// --- In-memory cache ---
interface CacheData {
    memberDisplayList: MemberDisplayInfo[];
    pendingInvites: PendingInvitation[];
}
const membersCache = new Map<string, CacheData>();


const capitalizeRole = (role: string) => {
  if (!role) return '';
  return role.charAt(0).toUpperCase() + role.slice(1);
};

const roleOrder: Record<GroupRole, number> = {
  owner: 0,
  admin: 1,
  member: 2,
};

const MembersContent: React.FC<MembersContentProps> = ({ groupId, currentUser }) => {
  const [memberDisplayList, setMemberDisplayList] = useState<MemberDisplayInfo[]>([]);
  const [pendingInvites, setPendingInvites] = useState<PendingInvitation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [currentUserRole, setCurrentUserRole] = useState<GroupRole | null>(null);

  const fetchMemberData = async (forceRefresh = false) => {
    if (!groupId) return;

    if (!forceRefresh && membersCache.has(groupId)) {
      const cachedData = membersCache.get(groupId)!;
      setMemberDisplayList(cachedData.memberDisplayList);
      setPendingInvites(cachedData.pendingInvites);
      const self = cachedData.memberDisplayList.find(m => m.user_id === currentUser.user_id);
      if (self) setCurrentUserRole(self.role as GroupRole);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const [balanceRes, membersRes, invitesRes, selfRoleRes] = await Promise.all([
        api.get<GroupBalanceSummary>(`/groups/${groupId}/balances`),
        api.get<GroupMember[]>(`/groups/${groupId}/members`),
        api.get<PendingInvitation[]>(`/groups/${groupId}/invitations`),
        api.get<{ role: GroupRole }>(`/groups/${groupId}/user-role`)
      ]);

      const balances = balanceRes.data.balances;
      const groupMembers = membersRes.data;
      const pendingInvitesData = invitesRes.data;
      setCurrentUserRole(selfRoleRes.data.role);

      const memberDetailsMap = new Map<number, { role: GroupRole, joined_at: string, profile_image_url?: string }>();
      groupMembers.forEach(member => {
        if (member.user) {
          memberDetailsMap.set(member.user.user_id, { 
              role: member.role, 
              joined_at: member.joined_at,
              profile_image_url: member.user.profile_image_url
          });
        }
      });

      const combinedData = balances.map(balance => {
        const details = memberDetailsMap.get(balance.user_id);
        return {
          ...balance,
          role: details?.role || 'member',
          joined_at: details?.joined_at,
          profile_image_url: details?.profile_image_url
        };
      });

      combinedData.sort((a, b) => {
        const roleA = roleOrder[a.role as GroupRole] ?? 99;
        const roleB = roleOrder[b.role as GroupRole] ?? 99;
        if (roleA !== roleB) return roleA - roleB;
        return a.username.localeCompare(b.username);
      });

      setMemberDisplayList(combinedData);
      setPendingInvites(pendingInvitesData);
      membersCache.set(groupId, { memberDisplayList: combinedData, pendingInvites: pendingInvitesData });
    } catch (err) {
      console.error("Failed to fetch member data:", err);
      setError("Could not load member details. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMemberData();
  }, [groupId]);

  const handleInviteModalClose = () => {
    setIsInviteModalOpen(false);
    fetchMemberData(true); // Always refresh when invite modal is closed
  };

  const handleProfileUpdateAndClose = () => {
    setIsProfileModalOpen(false);
    fetchMemberData(true); // Force a refresh
  };

  const handleProfileClose = () => {
    setIsProfileModalOpen(false);
  };

  const getBalanceDisplayProperties = (netAmount: number) => {
    const amount = Math.abs(netAmount);
    const formattedAmount = formatCurrency(amount, { rounding: true });

    if (netAmount > 0) { // User owes money
      return {
        text: `Owes: ${formattedAmount}`,
        rowBgColor: 'bg-red-100 hover:bg-red-200',
        rowTextColor: 'text-red-700',
      };
    } else if (netAmount < 0) { // User is owed money
      return {
        text: `Owed ${formattedAmount}`,
        rowBgColor: 'bg-green-100 hover:bg-green-200',
        rowTextColor: 'text-green-700',
      };
    } else { // Settled up
      return {
        text: 'Settled',
        rowBgColor: 'bg-gray-50 hover:bg-gray-100',
        rowTextColor: 'text-gray-700',
      };
    }
  };

  const handleMemberClick = (userId: number) => {
    setSelectedUserId(userId);
    setIsProfileModalOpen(true);
  };

  if (isLoading) {
    return <div className="text-center py-10">Loading members...</div>;
  }

  if (error) {
    return <div className="bg-white shadow-sm p-6 rounded-lg text-red-500">{error}</div>;
  }

  return (
    <div className="bg-white shadow-sm p-6 rounded-lg">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold text-gray-700">Group Members</h2>
        <button
          onClick={() => setIsInviteModalOpen(true)}
          className="flex items-center bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded-lg shadow-md transition duration-150 ease-in-out text-sm"
        >
          <PlusCircleIcon className="h-5 w-5 mr-2" />
          Add Member
        </button>
      </div>
      {memberDisplayList.length === 0 && pendingInvites.length === 0 ? (
        <p className="text-gray-500">No members found in this group yet.</p>
      ) : (
        <>
        {memberDisplayList.length > 0 && 
            <ul className="mt-4 space-y-2">
            {memberDisplayList.map((member) => {
                const balanceProps = getBalanceDisplayProperties(member.net_amount);
                const isCurrentUser = member.user_id === currentUser.user_id;

                return (
                <li
                    key={member.user_id}
                    className={`p-4 rounded-lg flex justify-between items-center transition-colors cursor-pointer ${balanceProps.rowBgColor} ${balanceProps.rowTextColor}`}
                    onClick={() => handleMemberClick(member.user_id)}
                >
                    <div className="flex items-center">
                        <img 
                            src={member.profile_image_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(member.username)}&background=random&length=2`}
                            alt={`${member.username}'s profile picture`}
                            className="w-10 h-10 rounded-full mr-4 object-cover"
                        />
                        <div className="flex flex-col">
                            <span className={`font-medium ${isCurrentUser ? 'font-bold' : ''}`}>{member.username}</span>
                            <span className="text-sm text-gray-500">{capitalizeRole(member.role)}</span>
                        </div>
                    </div>
                    <div className="font-semibold text-sm">{balanceProps.text}</div>
                </li>
                );
            })}
            </ul>
        }

        {/* Pending Invitations */}
        {pendingInvites.length > 0 && (
            <div className="mt-8">
                <h3 className="text-lg font-semibold text-gray-600 mb-2">Pending Invitations</h3>
                <ul className="space-y-2">
                    {pendingInvites.map((invite) => (
                        <li key={invite.invitation_id} className="p-3 bg-yellow-50 rounded-lg flex items-center justify-between">
                            <div className="flex items-center">
                                <img 
                                    src={invite.invitee.profile_image_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(invite.invitee.username)}&background=random&length=2`}
                                    alt={`${invite.invitee.username}'s profile picture`}
                                    className="w-8 h-8 rounded-full mr-3 object-cover"
                                />
                                <span className="font-medium text-yellow-800">{invite.invitee.username}</span>
                            </div>
                            <span className="text-xs text-gray-500">
                                Invited by {invite.inviter.username}
                            </span>
                        </li>
                    ))}
                </ul>
            </div>
        )}
        </>
      )}

      <InviteMemberModal
        isOpen={isInviteModalOpen}
        onClose={handleInviteModalClose}
        groupId={groupId}
      />

      {isProfileModalOpen && selectedUserId && (
        <UserProfileModal
          userId={selectedUserId}
          groupId={groupId}
          currentUserId={currentUser.user_id}
          currentUserRole={currentUserRole}
          onClose={handleProfileClose}
          onActionCompleted={handleProfileUpdateAndClose}
        />
      )}
    </div>
  );
};

export default MembersContent; 