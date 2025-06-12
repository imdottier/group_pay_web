'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { ArrowLeftIcon } from '@heroicons/react/24/solid';
import Link from 'next/link';

export default function CreateGroupPage() {
  const [groupName, setGroupName] = useState('');
  const [description, setDescription] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!groupName.trim()) {
      setError('Group name is required.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const payload = {
        group_name: groupName.trim(),
        description: description.trim() || null,
      };
      
      const response = await api.post('/groups/', payload);
      
      // On success, redirect to the new group's page or the main dashboard
      // router.push(`/groups/${response.data.group_id}`);
      router.push('/'); // Redirect to dashboard for now

    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to create group. Please try again.';
      setError(errorMsg);
      console.error("Failed to create group:", err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-12 max-w-2xl">
      <div className="mb-8">
        <Link href="/" className="inline-flex items-center text-gray-600 hover:text-gray-900 transition-colors">
          <ArrowLeftIcon className="h-5 w-5 mr-2" />
          Back to Your Groups
        </Link>
      </div>

      <div className="bg-white p-8 rounded-2xl shadow-lg">
        <h1 className="text-3xl font-bold text-gray-800 mb-2">Create a New Group</h1>
        <p className="text-gray-500 mb-8">Groups help you organize expenses with friends and family.</p>

        <form onSubmit={handleSubmit}>
          <div className="mb-6">
            <label htmlFor="groupName" className="block text-lg font-medium text-gray-800 mb-2">
              Group Name
            </label>
            <input
              type="text"
              id="groupName"
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-lg text-gray-900 transition"
              required
              maxLength={100}
              placeholder="e.g., Trip to Bali, Apartment Flatmates"
            />
          </div>

          <div className="mb-8">
            <label htmlFor="description" className="block text-lg font-medium text-gray-800 mb-2">
              Description <span className="text-sm text-gray-500">(Optional)</span>
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-lg text-gray-900 transition"
              maxLength={255}
              placeholder="e.g., A group for our upcoming vacation expenses."
            />
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 text-red-700 border-l-4 border-red-400 rounded-r-lg">
              <p className="font-semibold">Error</p>
              <p>{error}</p>
            </div>
          )}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={isLoading}
              className="px-8 py-3 text-lg font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-wait transition-all duration-150"
            >
              {isLoading ? 'Creating...' : 'Create Group'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
} 