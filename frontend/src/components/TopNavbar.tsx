'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';

// Placeholder icons (replace with actual icons later)
const BellIcon = () => <span>🔔</span>;
const UserCircleIcon = () => <span>👤</span>;

const TopNavbar = () => {
    const router = useRouter();
    const pathname = usePathname();
    const [isProfileDropdownOpen, setIsProfileDropdownOpen] = useState(false);
    const [isNotificationDropdownOpen, setIsNotificationDropdownOpen] = useState(false);

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
                            onClick={() => setIsNotificationDropdownOpen(!isNotificationDropdownOpen)}
                            className="hover:text-gray-300 focus:outline-none p-2"
                        >
                            <BellIcon />
                        </button>
                        {isNotificationDropdownOpen && (
                            <div className="absolute right-0 mt-2 w-48 bg-white text-black rounded-md shadow-lg py-1 z-50">
                                <p className="px-4 py-2 text-sm text-gray-700">No new notifications</p>
                            </div>
                        )}
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