'use client';

import { useEffect, useState, useRef } from 'react';
import api from '@/lib/api';
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline';
import { formatCurrency } from '@/lib/utils';
import Link from 'next/link';

interface User {
  user_id: number;
  username: string;
  // email, full_name can be added if needed and available
}

interface Payment {
  payment_id: number;
  group_id: number;
  payer_id: number;
  payee_id: number;
  bill_id?: number | null;
  amount: number; // Assuming backend sends number, will be parsed from Decimal
  notes?: string | null;
  payment_date?: string | null; // Date string from backend
  created_at: string; // DateTime string from backend
  payer?: User; // Optional nested user details
  payee?: User; // Optional nested user details
}

interface PaymentsContentProps {
  groupId: string;
  initialPayments?: Payment[];
  initialHasMore?: boolean;
}

const ITEMS_PER_PAGE = 20;

type SortOption = 'created_at-desc' | 'amount-desc' | 'amount-asc';
type FilterType = 'all' | 'involving' | 'from_member' | 'to_member' | 'between';

// --- In-memory cache for payments ---
const paymentsCache = new Map<string, { payments: Payment[], hasMore: boolean }>();

// --- Helper to fetch members, with its own cache ---
const membersCache = new Map<string, User[]>();
const fetchGroupMembers = async (groupId: string): Promise<User[]> => {
    if (membersCache.has(groupId)) {
        return membersCache.get(groupId)!;
    }
    try {
        const response = await api.get<any[]>(`/groups/${groupId}/members`);
        const members = response.data.map(m => m.user);
        membersCache.set(groupId, members);
        return members;
    } catch (error) {
        console.error("Failed to fetch group members", error);
        return []; // Return empty on error
    }
};

const formatDate = (dateString?: string | null) => {
  if (!dateString) return 'N/A';
  try {
    return new Date(dateString).toLocaleDateString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric'
    });
  } catch (e) {
    return dateString; // Return original if parsing fails
  }
};

const PaymentsContent: React.FC<PaymentsContentProps> = ({ groupId, initialPayments, initialHasMore }) => {
  const [payments, setPayments] = useState<Payment[]>(initialPayments || []);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoading, setIsLoading] = useState(!initialPayments);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(initialHasMore ?? true);
  const [sortOption, setSortOption] = useState<SortOption>('created_at-desc');

  // New state for filtering
  const [filterType, setFilterType] = useState<FilterType>('all');
  const [groupMembers, setGroupMembers] = useState<User[]>([]);
  const [memberA, setMemberA] = useState<number | null>(null);
  const [memberB, setMemberB] = useState<number | null>(null);

  useEffect(() => {
    fetchGroupMembers(groupId).then(setGroupMembers);
  }, [groupId]);

  useEffect(() => {
      const fetchPayments = async () => {
        setIsLoading(true);
          setError(null);
      
      const [sortBy, sortOrder] = sortOption.split('-');
      const cacheKey = `payments-${groupId}-p${currentPage}-s${sortOption}-f${filterType}-a${memberA}-b${memberB}`;

      if (paymentsCache.has(cacheKey)) {
        const cached = paymentsCache.get(cacheKey)!;
        setPayments(cached.payments);
        setHasMore(cached.hasMore);
        setIsLoading(false);
        return;
      }

      const params: any = {
          skip: (currentPage - 1) * ITEMS_PER_PAGE,
          limit: ITEMS_PER_PAGE,
          sort_by: sortBy,
          sort_order: sortOrder,
          filter_type: filterType,
      };

      if (memberA) params.member_a_id = memberA;
      if (memberB && filterType === 'between') params.member_b_id = memberB;


      try {
        const response = await api.get<Payment[]>('/groups/' + groupId + '/payments', { params });
        const fetchedPayments = response.data;
        const newHasMore = fetchedPayments.length === ITEMS_PER_PAGE;
        
        setPayments(fetchedPayments);
        setHasMore(newHasMore);
        paymentsCache.set(cacheKey, { payments: fetchedPayments, hasMore: newHasMore });

      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to fetch payments.');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

      fetchPayments();
  }, [currentPage, groupId, sortOption, filterType, memberA, memberB]);

  const handleNextPage = () => {
    if (hasMore) {
        setCurrentPage(prev => prev + 1);
    }
  };

  const handlePrevPage = () => {
    setCurrentPage(prev => Math.max(prev - 1, 1));
  };

  const resetAndFetch = () => {
    setCurrentPage(1);
    setPayments([]);
    setHasMore(true);
    paymentsCache.clear();
  };

  const handleSortChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSortOption(e.target.value as SortOption);
    resetAndFetch();
  };

  const handleFilterTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFilterType(e.target.value as FilterType);
    setMemberA(null);
    setMemberB(null);
    resetAndFetch();
  };
  
  const handleMemberAChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value ? Number(e.target.value) : null;
    setMemberA(value);
    setMemberB(null); // Reset B if A changes
    resetAndFetch();
  };

  const handleMemberBChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value ? Number(e.target.value) : null;
    setMemberB(value);
    resetAndFetch();
  };

  return (
    <div className="bg-white shadow-sm p-6 rounded-lg">
      <div className="mb-6 space-y-4">
        <div className="flex justify-between items-center">
            <div className="flex items-center space-x-4">
                <label htmlFor="sort-payments" className="text-sm font-medium text-gray-900">Sort by:</label>
                <select 
                    id="sort-payments" 
                    value={sortOption} 
                    onChange={handleSortChange}
                    className="block pl-3 pr-10 py-2 text-base bg-gray-50 border border-gray-500 focus:outline-none focus:ring-gray-600 focus:border-gray-600 sm:text-sm rounded-md text-gray-900"
                >
                    <option value="created_at-desc">Newest First</option>
                    <option value="amount-desc">Amount: High to Low</option>
                    <option value="amount-asc">Amount: Low to High</option>
                </select>
            </div>
            <Link href={`/groups/${groupId}/payments/create`} passHref>
              <button className="bg-indigo-600 text-white font-semibold py-2 px-4 rounded-md hover:bg-indigo-700 transition ease-in-out duration-150">
                + Add Payment
              </button>
            </Link>
        </div>
        <div className="flex items-center space-x-4">
             <label htmlFor="filter-type" className="text-sm font-medium text-gray-900">Filter by:</label>
             <select 
                id="filter-type" 
                value={filterType} 
                onChange={handleFilterTypeChange}
                className="block pl-3 pr-10 py-2 text-base bg-gray-50 border border-gray-500 focus:outline-none focus:ring-gray-600 focus:border-gray-600 sm:text-sm rounded-md text-gray-900"
            >
                <option value="all">All Payments</option>
                <option value="involving">Involving</option>
                <option value="from_member">From</option>
                <option value="to_member">To</option>
                <option value="between">Between</option>
            </select>
            
            {(filterType !== 'all') && (
                 <select 
                    id="member-a" 
                    value={memberA ?? ''}
                    onChange={handleMemberAChange}
                    className="block pl-3 pr-10 py-2 text-base bg-gray-50 border border-gray-500 focus:outline-none focus:ring-gray-600 focus:border-gray-600 sm:text-sm rounded-md text-gray-900"
                >
                    <option value="" disabled>Select Member</option>
                    {groupMembers.map(m => <option key={m.user_id} value={m.user_id}>{m.username}</option>)}
                </select>
            )}

            {filterType === 'between' && (
                <>
                    <span className="text-gray-700">and</span>
                    <select 
                        id="member-b" 
                        value={memberB ?? ''}
                        onChange={handleMemberBChange}
                        disabled={!memberA}
                        className="block pl-3 pr-10 py-2 text-base bg-gray-50 border border-gray-500 focus:outline-none focus:ring-gray-600 focus:border-gray-600 sm:text-sm rounded-md text-gray-900 disabled:bg-gray-200"
                    >
                        <option value="" disabled>Select Member</option>
                        {groupMembers.filter(m => m.user_id !== memberA).map(m => <option key={m.user_id} value={m.user_id}>{m.username}</option>)}
                    </select>
                </>
            )}
        </div>
      </div>

      {isLoading && <p className="text-center text-gray-500 py-4">Loading payments...</p>}
      {error && <p className="text-red-500 text-center py-4">{error}</p>}

      {!isLoading && !error && (
        <>
      {payments.length === 0 ? (
        <p className="text-gray-500">No payments recorded for this group yet.</p>
      ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Payer</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Payee</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Notes</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {payments.map((payment) => (
                  <tr key={payment.payment_id}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatDate(payment.payment_date || payment.created_at)}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{payment.payer?.username || 'N/A'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatCurrency(payment.amount, { rounding: false })}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{payment.payee?.username || 'N/A'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 truncate max-w-xs" title={payment.notes || ''}>{payment.notes || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          )}

          <div className="mt-6 flex justify-center items-center space-x-4">
            <button
              onClick={handlePrevPage}
              disabled={currentPage === 1 || isLoading}
              className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
            >
              <ChevronLeftIcon className="h-5 w-5" />
            </button>
            <span className="text-sm text-gray-700">
              Page {currentPage}
            </span>
            <button
              onClick={handleNextPage}
              disabled={!hasMore || isLoading}
              className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
            >
              <ChevronRightIcon className="h-5 w-5" />
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default PaymentsContent; 