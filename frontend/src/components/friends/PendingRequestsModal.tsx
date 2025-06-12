'use client';

import { useState } from 'react';
import api from '@/lib/api';
import { User, Friendship, FriendshipStatus } from '@/types';

interface PendingRequestsModalProps {
  isOpen: boolean;
  onClose: () => void;
  receivedRequests: Friendship[];
  sentRequests: Friendship[];
  onAction: () => void; // Callback to refresh parent state
}

const PendingRequestsModal = ({ isOpen, onClose, receivedRequests, sentRequests, onAction }: PendingRequestsModalProps) => {
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState<'received' | 'sent'>('received');

  const handleResponse = async (requesterId: number, status: FriendshipStatus.accepted | FriendshipStatus.declined) => {
    setLoading(prev => ({ ...prev, [requesterId]: true }));
    try {
      if (status === FriendshipStatus.accepted) {
        await api.put(`/friends/request/${requesterId}/accept`);
      } else {
        await api.delete(`/friends/request/${requesterId}`);
      }
      onAction(); // Notify parent to refetch data
    } catch (err: any) {
      alert(`Error: ${err.response?.data?.detail || 'Could not respond to request.'}`);
    } finally {
      setLoading(prev => ({ ...prev, [requesterId]: false }));
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-[rgba(0,0,0,0.5)] backdrop-blur-sm z-50 flex justify-center items-center">
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold text-gray-900">Pending Friend Requests</h2>
          <button onClick={onClose} className="text-gray-600 hover:text-gray-900">&times;</button>
        </div>
        
        {/* Tab Buttons */}
        <div className="mb-4 flex p-1 bg-gray-200/70 rounded-lg shadow-inner">
            <button
              onClick={() => setActiveTab('received')}
              className={`flex-1 py-2 px-4 text-sm font-medium rounded-lg transition-all duration-200 ${
                activeTab === 'received' ? 'bg-white text-black shadow' : 'text-black hover:bg-white/60'
              }`}
            >
              Received ({receivedRequests.length})
            </button>
            <button
              onClick={() => setActiveTab('sent')}
              className={`flex-1 py-2 px-4 text-sm font-medium rounded-lg transition-all duration-200 ${
                activeTab === 'sent' ? 'bg-white text-black shadow' : 'text-black hover:bg-white/60'
              }`}
            >
              Sent ({sentRequests.length})
            </button>
        </div>
        
        <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-2">
          {activeTab === 'received' && (
            <div>
              <div className="space-y-3">
                {receivedRequests.length === 0 ? (
                  <p className="text-gray-600 text-center py-4">No incoming requests.</p>
                ) : (
                  receivedRequests.map(req => (
                    <div key={req.requester_id} className="flex justify-between items-center p-3 bg-gray-100 rounded-md">
                      <div>
                        <p className="font-semibold text-gray-800">{req.requester.username}</p>
                        <p className="text-sm text-gray-600">{req.requester.email}</p>
                      </div>
                      <div className="flex space-x-2">
                        <button
                          onClick={() => handleResponse(req.requester_id, FriendshipStatus.accepted)}
                          disabled={loading[req.requester_id]}
                          className="px-3 py-1 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-500 text-sm font-medium"
                        >
                          Accept
                        </button>
                        <button
                          onClick={() => handleResponse(req.requester_id, FriendshipStatus.declined)}
                          disabled={loading[req.requester_id]}
                          className="px-3 py-1 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:bg-gray-500 text-sm font-medium"
                        >
                          Decline
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {activeTab === 'sent' && (
            <div>
              <div className="space-y-3">
                {sentRequests.length === 0 ? (
                  <p className="text-gray-600 text-center py-4">No outgoing requests.</p>
                ) : (
                  sentRequests.map(req => (
                    <div key={req.addressee_id} className="flex justify-between items-center p-3 bg-gray-50 rounded-md">
                      <div>
                        <p className="font-semibold text-gray-800">{req.addressee.username}</p>
                        <p className="text-sm text-gray-600">{req.addressee.email}</p>
                      </div>
                      <span className="text-sm text-gray-500 font-medium">Pending</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PendingRequestsModal; 