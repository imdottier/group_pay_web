'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import TopNavbar from '@/components/TopNavbar';

// Placeholder for a TopNavbar component we will create
// import TopNavbar from '@/components/TopNavbar'; 

export default function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [isClient, setIsClient] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    setIsClient(true);
    const token = localStorage.getItem('token');
    if (token) {
      setIsAuthenticated(true);
    } else {
      setIsAuthenticated(false);
      if (pathname !== '/login') {
        router.push('/login');
      }
    }
  }, [router, pathname]);

  // Consistent loading state until client-side checks are fully complete
  if (!isClient) {
    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100">
            <p className="text-gray-700">Loading application...</p>
        </div>
    );
  }

  // After client is confirmed, if not authenticated and not on login, show loading (or null) while redirecting
  if (!isAuthenticated && pathname !== '/login') {
    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100">
            <p className="text-gray-700">Redirecting to login...</p>
        </div>
    ); // Or return null if you prefer no flash of content
  }
  
  // If authenticated or on the login page (which handles its own rendering if no token),
  // render the main layout and children.
  return (
    <div className="min-h-screen flex flex-col">
      <TopNavbar />
      <main className="flex-grow w-full px-4 py-4 bg-gray-100">
        {children}
      </main>
      <footer className="bg-gray-100 text-center p-4 text-sm text-gray-600">
        © Group Expense Tracker
      </footer>
    </div>
  );
} 