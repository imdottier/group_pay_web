import React, { useRef, useEffect } from 'react';
import useSWR from 'swr';
import api from '@/lib/api';

interface Notification {
  id: number;
  message: string;
  created_at: string;
  read: boolean;
}

interface NotificationsPanelProps {
  open: boolean;
  onClose: () => void;
  onNotificationRead?: () => void;
}

const fetcher = (url: string) => api.get(url).then(res => res.data);

const NotificationsPanel: React.FC<NotificationsPanelProps> = ({ open, onClose, onNotificationRead }) => {
  const { data, error, isLoading, mutate } = useSWR<Notification[]>(open ? '/notifications/me' : null, fetcher);
  const panelRef = useRef<HTMLDivElement>(null);

  // Close when clicking outside
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open, onClose]);

  if (!open) return null;

  const handleNotificationClick = async (noti: Notification) => {
    if (!noti.read) {
      try {
        await api.post(`/notifications/${noti.id}/read`);
        if (onNotificationRead) onNotificationRead();
        mutate();
      } catch (e) {
        // Optionally show error
      }
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-40 flex items-start justify-end px-4 pt-16 pointer-events-none">
      <div
        ref={panelRef}
        className="w-full max-w-sm bg-white shadow-xl rounded-lg overflow-hidden pointer-events-auto border border-gray-200"
        style={{ maxHeight: 400 }}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <span className="font-semibold text-lg text-gray-800">Notifications</span>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 p-1 rounded">
            <span className="sr-only">Close</span>
            &times;
          </button>
        </div>
        <div className="overflow-y-auto" style={{ maxHeight: 340 }}>
          {isLoading && <div className="p-4 text-gray-500">Loading...</div>}
          {error && <div className="p-4 text-red-500">Failed to load notifications.</div>}
          {data && data.length === 0 && <div className="p-4 text-gray-500">No notifications.</div>}
          {data && data.length > 0 && (
            <ul>
              {[...data].sort((a, b) => b.id - a.id).map((noti) => (
                <li
                  key={noti.id}
                  onClick={() => handleNotificationClick(noti)}
                  className={`px-4 py-3 border-b last:border-b-0 transition-colors cursor-pointer ${noti.read ? 'bg-gray-50' : 'bg-indigo-50'} ${!noti.read ? 'font-bold' : ''}`}
                >
                  <div className="text-sm text-gray-800 mb-1">{noti.message}</div>
                  <div className="text-xs text-gray-500">{new Date(noti.created_at).toLocaleString()}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};

export default NotificationsPanel; 