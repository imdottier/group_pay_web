"use client";

import { Suspense } from "react";
import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

export default function Page() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-100"><div className="text-center"><p className="text-lg font-semibold text-gray-700">Please wait, authenticating...</p><div className="mt-4 animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500 mx-auto"></div></div></div>}>
      <AuthCallbackContent />
    </Suspense>
  );
}

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const token = searchParams.get('token');

    if (token) {
      // Store the token in localStorage
      localStorage.setItem('token', token);
      
      // Redirect to the home page or a dashboard
      // The user is now authenticated
      router.push('/'); 
    } else {
      // If no token is found, something went wrong.
      // Redirect to the login page with an error message.
      console.error("Google Auth Callback Error: No token received.");
      router.push('/login?error=google_auth_failed');
    }
  }, [router, searchParams]);

  return null;
} 