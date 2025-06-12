import PersonalPageTabs from '@/components/personal/PersonalPageTabs';

export default function PersonalPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Personal Dashboard</h1>
      <PersonalPageTabs />
    </div>
  );
} 