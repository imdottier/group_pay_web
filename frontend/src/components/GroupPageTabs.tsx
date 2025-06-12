'use client';

import React from 'react';

export type GroupTab = 'dashboard' | 'members' | 'bills' | 'payments' | 'activity' | 'settings';

interface GroupPageTabsProps {
  currentGroupId: string; // Keep for potential future use in tab definitions if needed
  activeTab: GroupTab;
  onTabChange: (tab: GroupTab) => void;
}

const GroupPageTabs: React.FC<GroupPageTabsProps> = ({ activeTab, onTabChange }) => {
  const tabs: { name: string; id: GroupTab }[] = [
    { name: 'Members', id: 'members' },
    { name: 'Bills', id: 'bills' },
    { name: 'Payments', id: 'payments' },
    { name: 'Activity', id: 'activity' },
    { name: 'Dashboard', id: 'dashboard' },
    // { name: 'Settings', id: 'settings' }, // Example for later
  ];

  return (
    <div className="bg-white shadow-sm mb-6">
      <nav className="-mb-px flex space-x-4 sm:space-x-8 px-2 sm:px-4" aria-label="Tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`whitespace-nowrap py-3 sm:py-4 px-1 border-b-2 font-medium text-sm focus:outline-none ${
              activeTab === tab.id
                ? 'border-indigo-500 text-indigo-600' // Active tab
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300' // Inactive tab
            }`}
            aria-current={activeTab === tab.id ? 'page' : undefined}
          >
            {tab.name}
          </button>
        ))}
      </nav>
    </div>
  );
};

export default GroupPageTabs; 