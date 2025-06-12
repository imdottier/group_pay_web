'use client';

import { useState, useEffect } from 'react';
import { User } from '@/types';
import api from '@/lib/api';

interface InviteMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
  groupId: string;
}

const InviteMemberModal = ({ isOpen, onClose, groupId }: InviteMemberModalProps) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [inviteStatus, setInviteStatus] = useState<Record<number, 'invited' | 'failed' | 'inviting' | null>>({});
  const [inviteError, setInviteError] = useState<Record<number, string | null>>({});

  useEffect(() => {
    // Reset state when modal is closed or opened
    if (!isOpen) {
      setTimeout(() => { // Allow for closing animation if any
        setSearchTerm('');
        setSearchResults([]);
        setLoading(false);
        setSearchError(null);
        setInviteStatus({});
        setInviteError({});
      }, 100);
    }
  }, [isOpen]);

  const handleSearch = async () => {
    if (searchTerm.trim().length < 2) {
      setSearchError('Please enter at least 2 characters to search.');
      setSearchResults([]);
      return;
    }
    setLoading(true);
    setSearchError(null);
    setInviteStatus({});
    setInviteError({});
    try {
      const response = await api.get<User[]>(`/users/search?query=${searchTerm}`);
      if (response.data.length === 0) {
        setSearchError('No users found matching your search.');
      }
      setSearchResults(response.data);
    } catch (err) {
      setSearchError('Failed to search for users.');
      console.error(err);
    }
    setLoading(false);
  };

  const handleInvite = async (inviteeId: number) => {
    if (inviteStatus[inviteeId] === 'invited' || inviteStatus[inviteeId] === 'inviting') return;

    setInviteStatus(prev => ({ ...prev, [inviteeId]: 'inviting' }));
    setInviteError(prev => ({ ...prev, [inviteeId]: null })); // Clear previous error

    try {
      await api.post(`/invitations/groups/${groupId}`, { invitee_id: inviteeId });
      setInviteStatus(prev => ({ ...prev, [inviteeId]: 'invited' }));
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'An unexpected error occurred.';
      setInviteStatus(prev => ({ ...prev, [inviteeId]: 'failed' }));
      setInviteError(prev => ({ ...prev, [inviteeId]: errorMessage }));
      console.error('Failed to send invitation:', err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex justify-center items-center">
      <div className="bg-white p-6 rounded-lg shadow-xl w-full max-w-md">
        <h2 className="text-xl font-semibold mb-4 text-gray-800">Invite New Member</h2>
        <div className="flex space-x-2">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search by username or email"
            className="flex-grow border border-gray-300 p-2 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 text-gray-900"
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 disabled:bg-indigo-400"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
        
        {searchError && searchResults.length === 0 && <p className="text-red-600 text-sm mt-2">{searchError}</p>}
        
        <div className="mt-4 max-h-60 overflow-y-auto">
          {searchResults.map((user) => (
            <div key={user.user_id} className="p-2 border-b border-gray-200">
                <div className="flex items-center justify-between">
                    <div>
                        <p className="font-semibold text-gray-800">{user.username}</p>
                        <p className="text-sm text-gray-600">{user.email}</p>
                    </div>
                    <button
                        onClick={() => handleInvite(user.user_id)}
                        disabled={inviteStatus[user.user_id] === 'invited' || inviteStatus[user.user_id] === 'inviting'}
                        className={`px-3 py-1 rounded text-sm font-medium text-white transition-colors duration-150 w-[70px] ${
                        inviteStatus[user.user_id] === 'invited'
                            ? 'bg-green-500 cursor-not-allowed'
                            : inviteStatus[user.user_id] === 'inviting'
                            ? 'bg-gray-400 cursor-wait'
                            : inviteStatus[user.user_id] === 'failed'
                            ? 'bg-red-600 hover:bg-red-700'
                            : 'bg-indigo-600 hover:bg-indigo-700'
                        }`}
                    >
                        {inviteStatus[user.user_id] === 'invited' ? 'Invited' : inviteStatus[user.user_id] === 'inviting' ? '...' : inviteStatus[user.user_id] === 'failed' ? 'Retry' : 'Invite'}
                    </button>
                </div>
                {inviteError[user.user_id] && (
                    <p className="text-red-600 text-xs mt-1">{inviteError[user.user_id]}</p>
                )}
            </div>
          ))}
        </div>

        <button onClick={onClose} className="mt-4 w-full border border-gray-300 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-100 font-medium">
          Done
        </button>
      </div>
    </div>
  );
};

export default InviteMemberModal; 