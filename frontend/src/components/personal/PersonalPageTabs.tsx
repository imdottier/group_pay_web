'use client';

import { useState } from 'react';
import TransactionsContent from './TransactionsContent';
import GraphContent from './GraphContent';

const PersonalPageTabs = () => {
  const [activeTab, setActiveTab] = useState('transactions');

  return (
    <div className="w-full">
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          <button
            onClick={() => setActiveTab('transactions')}
            className={`${
              activeTab === 'transactions'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            } whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium`}
          >
            Transactions
          </button>
          <button
            onClick={() => setActiveTab('graph')}
            className={`${
              activeTab === 'graph'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            } whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium`}
          >
            Graph
          </button>
        </nav>
      </div>

      <div className="mt-4">
        {activeTab === 'transactions' ? <TransactionsContent /> : <GraphContent />}
      </div>
    </div>
  );
};

export default PersonalPageTabs; 