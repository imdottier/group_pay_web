'use client';

import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import api from '@/lib/api';
import AddTransactionModal from './AddTransactionModal';
import { PlusIcon } from '@heroicons/react/24/outline';

interface Transaction {
  transaction_id: string;
  amount: number;
  transaction_date: string;
  notes: string;
  category: {
    id: string;
    name: string;
  };
}

const formatVND = (amount: number) => {
  // Amounts are typically stored as negative for expenses
  return new Intl.NumberFormat('vi-VN').format(Math.abs(amount)); 
};

const TRANSACTIONS_PER_PAGE = 10;

const TransactionsContent = () => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMoreTransactions, setHasMoreTransactions] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchTransactions = async (page: number) => {
    setLoading(true);
    try {
      const response = await api.get<Transaction[]>('/transactions/', {
        params: { limit: TRANSACTIONS_PER_PAGE, skip: (page - 1) * TRANSACTIONS_PER_PAGE }
      });
      setTransactions(prev => page === 1 ? response.data : [...prev, ...response.data]);
      setHasMoreTransactions(response.data.length === TRANSACTIONS_PER_PAGE);
    } catch (err) {
      setError('Failed to load transactions');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions(currentPage);
  }, [currentPage]);

  const handleTransactionAdded = (newTransaction: Transaction) => {
    setTransactions(prev => [newTransaction, ...prev]);
  };

  if (loading && transactions.length === 0) { // Show initial loading state only if no transactions are displayed yet
    return <div className="text-center py-4 text-gray-800">Loading transactions...</div>;
  }

  if (error) {
    return <div className="text-red-500 text-center py-4">{error}</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold text-gray-800">Your Transactions</h2>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          <PlusIcon className="h-5 w-5 mr-2" />
          Add Transaction
        </button>
      </div>

      <AddTransactionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onTransactionAdded={handleTransactionAdded}
      />

      {transactions.length === 0 && !loading && (
        <p className="text-center py-8 text-gray-500">No transactions found. Click "Add Transaction" to get started.</p>
      )}
      <div className="space-y-4">
        {transactions.map((transaction) => (
          <div
            key={transaction.transaction_id}
            className="bg-white rounded-lg p-4 shadow"
          >
            <div className="flex justify-between items-start">
              <div>
                <p className="text-gray-800">{format(new Date(transaction.transaction_date), 'MMM d, yyyy')}</p>
                <p className="text-gray-800">{transaction.notes}</p>
                <span className="inline-block bg-blue-100 text-blue-500 px-2 py-1 rounded text-sm">
                  {transaction.category.name}
                </span>
              </div>
              <p className="text-gray-800 font-semibold">
                {formatVND(transaction.amount)} ₫
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Pagination Controls */}
      {(transactions.length > 0 || currentPage > 1) && (
        <div className="mt-8 flex justify-center items-center space-x-3">
          <button 
            onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
            disabled={currentPage === 1 || loading}
            className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            Previous
          </button>
          <span className="text-sm text-gray-700">
            Page {currentPage}
          </span>
          <button 
            onClick={() => setCurrentPage(prev => prev + 1)}
            disabled={!hasMoreTransactions || loading}
            className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default TransactionsContent; 