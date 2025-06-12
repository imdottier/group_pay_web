'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';
import NotificationsPanel from './NotificationsPanel';
import useSWR from 'swr';
import api from '../lib/api';

// Placeholder icons (replace with actual icons later)
const BellIcon = () => <span>🔔</span>;
const UserCircleIcon = () => <span>👤</span>;

const TopNavbar = () => {
    const router = useRouter();
    const pathname = usePathname();
    const [isProfileDropdownOpen, setIsProfileDropdownOpen] = useState(false);
    const [showNotifications, setShowNotifications] = useState(false);
    const { data: unreadCount, mutate: mutateUnread } = useSWR<{ unread_count: number }>(
      '/notifications/me/unread-count',
      (url: string) => api.get(url).then((res: any) => res.data)
    );

    const handleLogout = () => {
        if (typeof window !== 'undefined') {
            localStorage.removeItem('access_token');
        }
        router.push('/login');
    };

    const isActive = (path: string) => pathname === path;

    return (
        <nav className="bg-blue-700 text-white shadow-md">
            <div className="w-full px-4 flex justify-between items-stretch h-full">
                {/* Left Side: items-stretch allows children to fill height */}
                <div className="flex items-stretch space-x-1">
                    <Link
                        href="/"
                        className={`flex items-center px-4 text-sm font-medium transition-colors duration-150 ease-in-out ${
                            isActive('/')
                                ? 'bg-blue-500 text-white'
                                : 'text-white hover:bg-blue-600 hover:text-white'
                        }`}
                    >
                        Groups
                    </Link>
                    <Link
                        href="/personal"
                        className={`flex items-center px-4 text-sm font-medium transition-colors duration-150 ease-in-out ${
                            isActive('/personal')
                                ? 'bg-blue-500 text-white'
                                : 'text-white hover:bg-blue-600 hover:text-white'
                        }`}
                    >
                        Personal
                    </Link>
                </div>

                {/* Right Side */}
                <div className="flex items-center space-x-4">
                    {/* Notification Icon & Dropdown */}
                    <div className="relative">
                        <button
                            onClick={() => setShowNotifications(true)}
                            className="hover:text-gray-300 focus:outline-none p-2 relative"
                        >
                            <BellIcon />
                            {unreadCount && unreadCount.unread_count > 0 && (
                              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 font-bold">
                                {unreadCount.unread_count}
                              </span>
                            )}
                        </button>
                        <NotificationsPanel open={showNotifications} onClose={() => setShowNotifications(false)} onNotificationRead={mutateUnread} />
                    </div>

                    {/* Profile Icon & Dropdown */}
                    <div className="relative">
                        <button
                            onClick={() => setIsProfileDropdownOpen(!isProfileDropdownOpen)}
                            className="hover:text-gray-300 focus:outline-none p-2"
                        >
                            <UserCircleIcon />
                        </button>
                        {isProfileDropdownOpen && (
                            <div className="absolute right-0 mt-2 w-48 bg-white text-black rounded-md shadow-lg py-1 z-50">
                                <Link href="/profile" passHref>
                                    <span className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 cursor-pointer">Your Profile</span>
                                </Link>
                                <Link href="/add-friend" passHref> 
                                    <span className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 cursor-pointer">Add Friend</span>
                                </Link>
                                <button
                                    onClick={handleLogout}
                                    className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                >
                                    Log out
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </nav>
    );
};

export default TopNavbar; 