import PersonalPageTabs from '@/components/personal/PersonalPageTabs';
import { Suspense } from 'react';

export default function PersonalPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Personal Dashboard</h1>
      <Suspense 
        fallback={
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-32 w-32 border-t-2 border-b-2 border-indigo-500"></div>
          </div>
        }
      >
        <PersonalPageTabs />
      </Suspense>
    </div>
  );
} 