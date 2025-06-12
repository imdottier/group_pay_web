'use client';

import React, { useState } from 'react';
import SpendingByCategoryChart from './SpendingByCategoryChart';
import MonthlySpendingChart from './MonthlySpendingChart';

interface DashboardContentProps {
  groupId: string;
}

const ANALYTICS_TABS = [
  { id: 'category', name: 'By Category' },
  { id: 'monthly', name: 'Monthly Trend' },
  // Add more tabs here as needed
];

type AnalyticsTab = 'category' | 'monthly';

const DashboardContent = ({ groupId }: DashboardContentProps) => {
  // Separate state for each chart
  const [categoryDate, setCategoryDate] = useState(new Date());
  const [monthlyYear, setMonthlyYear] = useState(new Date().getFullYear());
  const [activeTab, setActiveTab] = useState<AnalyticsTab>('category');

  // Month navigation for category chart
  const handlePreviousMonth = () => {
    setCategoryDate(prev => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
  };
  const handleNextMonth = () => {
    setCategoryDate(prev => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));
  };

  // Year navigation for monthly chart
  const handleMonthlyYearChange = (delta: number) => {
    setMonthlyYear((prev) => prev + delta);
  };

  const categoryYear = categoryDate.getFullYear();
  const categoryMonth = categoryDate.getMonth() + 1;

  return (
    <div className="bg-white shadow-sm p-6 rounded-lg">
      {/* Analytics Tabs */}
      <div className="mb-6">
        <nav className="-mb-px flex space-x-4 sm:space-x-8 px-2 sm:px-4" aria-label="Tabs">
          {ANALYTICS_TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as AnalyticsTab)}
              className={`whitespace-nowrap py-3 sm:py-4 px-1 border-b-2 font-medium text-sm focus:outline-none ${
                activeTab === tab.id
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
              aria-current={activeTab === tab.id ? 'page' : undefined}
            >
              {tab.name}
            </button>
          ))}
        </nav>
      </div>
      {/* Tab Content */}
      {activeTab === 'category' && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-gray-700">Monthly Spending Report</h2>
            <div className="flex items-center space-x-4 min-w-[240px] justify-between">
              <button
                onClick={handlePreviousMonth}
                className="px-2 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors"
                aria-label="Previous Month"
              >
                &#8592;
              </button>
              <span className="font-medium text-lg text-gray-800 min-w-[120px] text-center">
                {categoryDate.toLocaleString('default', { month: 'long' })} {categoryYear}
              </span>
              <button
                onClick={handleNextMonth}
                className="px-2 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors"
                aria-label="Next Month"
              >
                &#8594;
              </button>
            </div>
          </div>
          <SpendingByCategoryChart groupId={groupId} year={categoryYear} month={categoryMonth} />
        </div>
      )}
      {activeTab === 'monthly' && (
        <div>
          <div className="flex items-center mb-2 justify-between">
            <h3 className="text-lg font-semibold text-gray-700">Yearly Spending Trend</h3>
            <div className="flex items-center space-x-4 min-w-[180px] justify-between">
              <button
                onClick={() => handleMonthlyYearChange(-1)}
                className="px-2 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors"
                aria-label="Previous Year"
              >
                &#8592;
              </button>
              <span className="font-medium text-md text-gray-800 min-w-[60px] text-center">{monthlyYear}</span>
              <button
                onClick={() => handleMonthlyYearChange(1)}
                className="px-2 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors"
                aria-label="Next Year"
              >
                &#8594;
              </button>
            </div>
          </div>
          <MonthlySpendingChart groupId={groupId} year={monthlyYear} />
        </div>
      )}
    </div>
  );
};

export default DashboardContent; 