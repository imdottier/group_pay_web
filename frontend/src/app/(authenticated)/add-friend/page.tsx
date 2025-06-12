'use client';

import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { UserPlusIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import PendingRequestsModal from '@/components/friends/PendingRequestsModal';
import { User, Friendship } from '@/types';

const AddFriendPage = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<User[]>([]);
  const [friends, setFriends] = useState<Friendship[]>([]);
  const [receivedRequests, setReceivedRequests] = useState<Friendship[]>([]);
  const [sentRequests, setSentRequests] = useState<Friendship[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState({
    search: false,
    friends: true,
    pending: true,
    add: false,
  });
  const [error, setError] = useState('');

  // Fetch initial data
  useEffect(() => {
    const fetchCurrentUser = async () => {
        try {
            const response = await api.get<User>('/users/me');
            setCurrentUser(response.data);
        } catch (err) {
            console.error('Failed to fetch current user', err);
            setError('Could not identify current user.');
        }
    };

    const fetchFriends = async () => {
      try {
        setLoading(prev => ({ ...prev, friends: true }));
        const response = await api.get<Friendship[]>('/friends/');
        setFriends(response.data);
      } catch (err) {
        setError('Could not load friends list.');
        console.error(err);
      } finally {
        setLoading(prev => ({ ...prev, friends: false }));
      }
    };

    const fetchPendingRequests = async () => {
      try {
        setLoading(prev => ({ ...prev, pending: true }));
        const [receivedRes, sentRes] = await Promise.all([
          api.get<Friendship[]>('/friends/pending/received'),
          api.get<Friendship[]>('/friends/pending/sent')
        ]);
        setReceivedRequests(receivedRes.data);
        setSentRequests(sentRes.data);
      } catch (err) {
        console.error('Could not load pending requests.', err);
      } finally {
        setLoading(prev => ({ ...prev, pending: false }));
      }
    };
    fetchCurrentUser();
    fetchFriends();
    fetchPendingRequests();
  }, []);

  // Handle user search
  useEffect(() => {
    if (searchQuery.trim().length < 2) {
      setSearchResults([]);
      return;
    }

    const search = setTimeout(async () => {
      setLoading(prev => ({ ...prev, search: true }));
      try {
        const response = await api.get<User[]>('/users/search', {
          params: { query: searchQuery },
        });
        setSearchResults(response.data);
      } catch (err) {
        console.error('Search failed:', err);
      } finally {
        setLoading(prev => ({ ...prev, search: false }));
      }
    }, 500); // Debounce search

    return () => clearTimeout(search);
  }, [searchQuery]);

  const handleAddFriend = async (addresseeId: number) => {
    setLoading(prev => ({ ...prev, add: true }));
    try {
      await api.post('/friends/request', { addressee_id: addresseeId });
      alert('Friend request sent!');
      setSearchQuery('');
      setSearchResults([]);
    } catch (err: any) {
      alert(`Error: ${err.response?.data?.detail || 'Could not send request.'}`);
    } finally {
      setLoading(prev => ({ ...prev, add: false }));
    }
  };

  const refreshFriendshipData = () => {
    // This will be called when a request is accepted/declined in the modal
    // Refetch both friends and pending requests to update the UI
    api.get<Friendship[]>('/friends/').then(res => setFriends(res.data));
    // Refetch both sets of pending requests
    api.get<Friendship[]>('/friends/pending/received').then(res => setReceivedRequests(res.data));
    api.get<Friendship[]>('/friends/pending/sent').then(res => setSentRequests(res.data));
  };
  
  return (
    <main className="container mx-auto p-4 md:p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Manage Friends</h1>
          <button
            onClick={() => setIsModalOpen(true)}
            className="relative inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            Pending Requests
            {receivedRequests.length > 0 && (
              <span className="absolute -top-2 -right-2 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs">
                {receivedRequests.length}
              </span>
            )}
          </button>
        </div>

        {/* Add Friend Section */}
        <div className="bg-white p-6 rounded-lg shadow-md mb-8">
          <h2 className="text-xl font-semibold mb-4 text-gray-900">Add a Friend</h2>
          <div className="relative">
            <MagnifyingGlassIcon className="pointer-events-none absolute top-3.5 left-4 h-5 w-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by username or email..."
              className="w-full pl-11 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 text-gray-900 placeholder:text-gray-500"
            />
          </div>
          {loading.search && <p className="mt-2 text-gray-600">Searching...</p>}
          <div className="mt-2 space-y-2">
            {searchResults.map((user) => (
              <div key={user.user_id} className="flex items-center justify-between p-2 hover:bg-gray-50 rounded-md">
                <div>
                  <p className="font-semibold text-gray-900">{user.username}</p>
                  <p className="text-sm text-gray-600">{user.email}</p>
                </div>
                <button
                  onClick={() => handleAddFriend(user.user_id)}
                  disabled={loading.add}
                  className="flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 disabled:bg-gray-400"
                >
                  <UserPlusIcon className="h-5 w-5 mr-1" />
                  Add
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Friends List Section */}
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-xl font-semibold mb-4 text-gray-900">Your Friends</h2>
          {loading.friends ? (
            <p className="text-gray-800">Loading friends...</p>
          ) : friends.length > 0 && currentUser ? (
            <ul className="divide-y divide-gray-200">
              {friends.map(friendship => {
                  const friendUser = friendship.requester.user_id === currentUser.user_id 
                    ? friendship.addressee 
                    : friendship.requester;
                  
                  return (
                    <li key={friendUser.user_id} className="py-3 flex justify-between items-center">
                      <div>
                        <span className="font-medium text-gray-900">{friendUser.username}</span>
                        <p className="text-sm text-gray-600">{friendUser.email}</p>
                      </div>
                       <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 capitalize">
                        {friendship.status}
                       </span>
                    </li>
                  );
                })}
            </ul>
          ) : (
            <p className="text-gray-600">You haven't added any friends yet.</p>
          )}
        </div>
      </div>
      
      <PendingRequestsModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        receivedRequests={receivedRequests}
        sentRequests={sentRequests}
        onAction={refreshFriendshipData}
      />
    </main>
  );
};

export default AddFriendPage; 