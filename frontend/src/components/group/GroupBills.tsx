'use client';

import React, { useState, useEffect, useRef, Fragment } from 'react';
import api from '@/lib/api';
import Link from 'next/link';
import { formatCurrency, roundToNearest500, get_user_role } from '@/lib/utils';
import BillInfoModal from '@/components/bills/BillInfoModal';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { Dialog, Transition } from '@headlessui/react';

// Interfaces matching backend schemas
interface User {
  user_id: number;
  full_name: string | null;
  email: string;
  username: string;
}

interface UserBase { 
  user_id: number;
  username: string;
}

interface SimpleUserBalance {
  user: UserBase;
  balance: number; 
}

interface BillItemSplit {
  user: User;
  quantity: number;
}

interface BillItem {
  item_id: number;
  name: string;
  unit_price: number;
  quantity: number;
  bill_item_splits: BillItemSplit[];
}

interface InitialPayment {
  user: User;
  amount_paid: string;
}

interface BillPart {
  user: User;
  amount_owed: string;
}

interface BillPartWithAmount {
  user_id: number;
  percentage: number;
  amount_owed: number;
}

interface Bill {
  bill_id: number;
  group_id: number;
  created_by: number;
  created_at: string;
  title: string;
  description?: string;
  total_amount: number;
  split_method: 'equal' | 'exact' | 'item';
  initial_payments: InitialPayment[];
  items: BillItem[];
  bill_parts: BillPart[];
  split_summary_percentage: BillPartWithAmount[];
  bill_creator: User;
}

interface UserNetBalance {
  user_id: number;
  username: string;
  net_amount: number;
}

interface UserBalanceWithOther {
  other_user: User;
  net_amount_current_user_owes: number;
}

interface GroupBalanceSummary {
  group_id: number;
  balances: UserNetBalance[];
}

interface SettlementTransaction {
  payer: User;
  payee: User;
  amount: number;
}

interface GroupBillsProps {
  groupId: string;
  currentUser: any;
}

interface Member {
  user: User;
}

// In-memory Cache for GroupBills
const billsCache = new Map<string, Bill[]>();
const netBalancesCache = new Map<string, UserNetBalance[]>();
const allUserBalancesCache = new Map<string, SimpleUserBalance[]>();
const settlementsCache = new Map<string, SettlementTransaction[]>();

// Helper function to format date
const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

export const GroupBills: React.FC<GroupBillsProps> = ({ groupId, currentUser }) => {
  const [bills, setBills] = useState<Bill[]>([]);
  const [isLoadingBills, setIsLoadingBills] = useState(true);
  const [errorBills, setErrorBills] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const billsPerPage = 10;

  const [activeTab, setActiveTab] = useState<'overall_balances' | 'balance_with_user' | 'settlements'>('overall_balances');

  const [netBalances, setNetBalances] = useState<UserNetBalance[] | null>(null);
  const [isLoadingBalances, setIsLoadingBalances] = useState(false);
  const [errorBalances, setErrorBalances] = useState<string | null>(null);

  const [allUserBalances, setAllUserBalances] = useState<SimpleUserBalance[] | null>(null);
  const [isLoadingAllUserBalances, setIsLoadingAllUserBalances] = useState(false);
  const [errorAllUserBalances, setErrorAllUserBalances] = useState<string | null>(null);

  const [suggestedPayments, setSuggestedPayments] = useState<SettlementTransaction[] | null>(null);
  const [isLoadingSettlements, setIsLoadingSettlements] = useState(false);
  const [errorSettlements, setErrorSettlements] = useState<string | null>(null);

  const [usersMap, setUsersMap] = useState<Record<number, string>>({});
  const isMountedRef = useRef(true);

  const [selectedBill, setSelectedBill] = useState<Bill | null>(null);
  const [billToDelete, setBillToDelete] = useState<Bill | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const [userRole, setUserRole] = useState<string | null>(null);

  // Effect to fetch group members for usersMap
  useEffect(() => {
    isMountedRef.current = true;
    if (!groupId) return;
    const fetchGroupMembers = async () => {
      try {
        const response = await api.get<Member[]>(`/groups/${groupId}/members`);
        const members = response.data;
        const newUsersMap = members.reduce((acc: any, member: any) => {
          acc[member.user.user_id] = member.user.username || member.user.full_name;
          return acc;
        }, {});
        if (isMountedRef.current) {
          setUsersMap(newUsersMap);
        }
      } catch (error) {
        console.error("Failed to fetch group members:", error);
      }
    };
    fetchGroupMembers();
  }, [groupId]);

  // Fetch ONLY bills for now
  useEffect(() => {
    isMountedRef.current = true;
    if (!groupId) return;

    const fetchData = async () => {
      const cacheKey = `${groupId}-${currentPage}`;
      if (billsCache.has(cacheKey)) {
        setBills(billsCache.get(cacheKey)!);
        setIsLoadingBills(false);
        return;
      }

      setIsLoadingBills(true);
      setErrorBills(null);
      try {
        const billsResponse = await api.get<Bill[]>(`/groups/${groupId}/bills/`, {
          params: { skip: (currentPage - 1) * billsPerPage, limit: billsPerPage }
        });

        if (!isMountedRef.current) return;

        if (Array.isArray(billsResponse.data)) {
          setBills(billsResponse.data);
          billsCache.set(cacheKey, billsResponse.data);
        } else {
          setErrorBills("Invalid bills response format.");
        }
      } catch (error: any) {
        if (!isMountedRef.current) return;
        if (error.response?.status === 429) {
          setErrorBills("Too many requests. Please wait a moment and try again.");
        } else {
          setErrorBills("Failed to load bills for this group.");
        }
      } finally {
        if (isMountedRef.current) {
          setIsLoadingBills(false);
        }
      }
    };

    fetchData();
    return () => { isMountedRef.current = false; };
  }, [groupId, currentPage, billsPerPage, usersMap]);

  useEffect(() => {
    const fetchOverallBalances = async () => {
      if (netBalancesCache.has(groupId)) {
        setNetBalances(netBalancesCache.get(groupId)!);
        return;
      }
      setIsLoadingBalances(true);
      try {
        const response = await api.get<GroupBalanceSummary>(`/groups/${groupId}/balances`);
        setNetBalances(response.data.balances);
        netBalancesCache.set(groupId, response.data.balances);
        setErrorBalances(null);
      } catch (error) {
        console.error('Failed to fetch group balances:', error);
        setErrorBalances('Failed to load overall balances.');
      } finally {
        setIsLoadingBalances(false);
      }
    };

    const fetchAllUserBalances = async () => {
      if (allUserBalancesCache.has(groupId)) {
        setAllUserBalances(allUserBalancesCache.get(groupId)!);
        return;
      }
      setIsLoadingAllUserBalances(true);
      try {
        const response = await api.get<SimpleUserBalance[]>(`/groups/${groupId}/balances_with_all_members`);
        setAllUserBalances(response.data);
        allUserBalancesCache.set(groupId, response.data);
        setErrorAllUserBalances(null);
      } catch (error) {
        setErrorAllUserBalances('Failed to load balances with other users.');
      } finally {
        setIsLoadingAllUserBalances(false);
      }
    };

    const fetchSettlements = async () => {
      if (settlementsCache.has(groupId)) {
        setSuggestedPayments(settlementsCache.get(groupId)!);
        return;
      }
      setIsLoadingSettlements(true);
      try {
        const response = await api.get<{suggested_payments: SettlementTransaction[]}>(`/groups/${groupId}/settlements`);
        const roundedPayments = response.data.suggested_payments.map(p => ({ ...p, amount: roundToNearest500(p.amount) }));
        setSuggestedPayments(roundedPayments);
        settlementsCache.set(groupId, roundedPayments);
        setErrorSettlements(null);
      } catch (error) {
        setErrorSettlements('Failed to calculate settlements.');
      } finally {
        setIsLoadingSettlements(false);
      }
    };

    if (activeTab === 'overall_balances') {
      fetchOverallBalances();
    } else if (activeTab === 'balance_with_user') {
      fetchAllUserBalances();
    } else if (activeTab === 'settlements') {
      fetchSettlements();
    }
  }, [activeTab, groupId]);

  useEffect(() => {
    const fetchUserRole = async () => {
      if (!groupId) return;
      try {
        const response = await api.get<{ role: string }>(`/groups/${groupId}/user-role`);
        setUserRole(response.data.role);
      } catch (error) {
        console.error('Error fetching user role:', error);
      }
    };
    fetchUserRole();
  }, [groupId]);

  // Early returns (currentUser, isLoadingBills, errorBills)
  if (!currentUser) {
    return <div className="p-4 text-center">Loading user data...</div>;
  }
  // We only care about isLoadingBills and errorBills for now
  if (isLoadingBills) {
    return <div className="p-4 text-center">Loading bills...</div>;
  }
  if (errorBills) {
    return <div className="p-4 text-center text-red-500">Error loading bills: {errorBills}</div>;
  }

  const currentBillsToDisplay = bills;
  const hasMoreBills = bills.length === billsPerPage;

  const handleBillClick = (bill: Bill) => {
    setSelectedBill(bill);
  };

  const handleCloseModal = () => {
    setSelectedBill(null);
  };

  const handleDeleteClick = (e: React.MouseEvent, bill: Bill) => {
    e.stopPropagation(); // Prevent bill click
    setBillToDelete(bill);
    setIsDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!billToDelete) return;
    
    setIsDeleting(true);
    try {
      await api.delete(`/groups/${groupId}/bills/${billToDelete.bill_id}`);
      // Remove the deleted bill from the list
      setBills(bills.filter(b => b.bill_id !== billToDelete.bill_id));
      setIsDeleteModalOpen(false);
      setBillToDelete(null);
    } catch (error) {
      console.error('Error deleting bill:', error);
      // You might want to show an error toast here
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCancelDelete = () => {
    setIsDeleteModalOpen(false);
    setBillToDelete(null);
  };

  const canDeleteBill = (bill: Bill) => {
    if (!currentUser) return false;
    return bill.created_by === currentUser.user_id || userRole === 'admin' || userRole === 'owner';
  };

  return (
    <div className="w-full">
      {/* Section 2: Tabs for balances and settlements - MOVED TO TOP */}
      <div className="mt-8">
        <div className="mb-6 flex justify-around items-center p-1 bg-gray-200/70 rounded-lg shadow-inner">
          <button
              onClick={() => setActiveTab('overall_balances')}
              className={`flex-1 py-2.5 px-4 text-sm font-medium rounded-lg transition-all duration-200 ${
                activeTab === 'overall_balances'
                  ? 'bg-white text-black shadow'
                  : 'text-black hover:bg-white/60'
              }`}
            >
              Overall Balances
            </button>
            <button
              onClick={() => setActiveTab('balance_with_user')}
              className={`flex-1 py-2.5 px-4 text-sm font-medium rounded-lg transition-all duration-200 ${
                activeTab === 'balance_with_user'
                  ? 'bg-white text-black shadow'
                  : 'text-black hover:bg-white/60'
              }`}
            >
              My Balances with Others
            </button>
            <button
              onClick={() => setActiveTab('settlements')}
              className={`flex-1 py-2.5 px-4 text-sm font-medium rounded-lg transition-all duration-200 ${
                activeTab === 'settlements'
                  ? 'bg-white text-black shadow'
                  : 'text-black hover:bg-white/60'
              }`}
            >
              Settle Up
            </button>
        </div>
      
        {/* Content based on activeTab */}
        {activeTab === 'overall_balances' && (
          <div className="p-4 bg-white rounded-lg shadow-inner">
            <h3 className="text-lg font-semibold text-gray-800 mb-3">Overall Group Balances</h3>
            {isLoadingBalances && <p className="text-center text-gray-500 py-4">Loading balances...</p>}
            {errorBalances && <p className="text-center text-red-500 py-4">{errorBalances}</p>}
            {netBalances && netBalances.length > 0 && (
                <ul className="space-y-2">
                    {netBalances.map(balance => (
                        <li key={balance.user_id} className={`py-3 px-4 flex justify-between items-center rounded-lg shadow-sm text-sm sm:text-base
                            ${balance.net_amount > 0 ? 'bg-red-100 text-red-700' :
                            balance.net_amount < 0 ? 'bg-green-100 text-green-700' :
                            'bg-gray-100 text-gray-700'}`}>
                            <span className="font-medium">{usersMap[balance.user_id] || 'Unknown User'}</span>
                            <span className="font-semibold">
                                {balance.net_amount > 0 && `Owes ${formatCurrency(balance.net_amount)}`}
                                {balance.net_amount < 0 && `Owed ${formatCurrency(Math.abs(balance.net_amount))}`}
                                {balance.net_amount === 0 && 'Settled up'}
                            </span>
                        </li>
                    ))}
                </ul>
            )}
            {!isLoadingBalances && !errorBalances && netBalances && netBalances.length === 0 && (
                <p className="text-center text-gray-500 py-4">No balances to display for this group.</p>
            )}
          </div>
        )}
        {activeTab === 'balance_with_user' && (
          <div className="p-4 bg-white rounded-lg shadow-inner">
            <h3 className="text-lg font-semibold text-gray-800 mb-3">Your Balances with Other Members</h3>
            {isLoadingAllUserBalances && <p className="text-center py-4">Loading balances with other users...</p>}
            {errorAllUserBalances && <p className="text-center text-red-500 py-4">{errorAllUserBalances}</p>}
            {allUserBalances && allUserBalances.length > 0 && (
            <ul className="space-y-2">
                {allUserBalances.map((balance) => (
                <li key={balance.user.user_id} className={`p-3 rounded-md text-sm
                    ${balance.balance > 0 ? 'bg-red-100 text-red-700' :
                    balance.balance < 0 ? 'bg-green-100 text-green-700' :
                    'bg-gray-100 text-gray-700'}`}>
                    {balance.balance > 0 ? 
                        <span>You owe <span className="font-semibold">{usersMap[balance.user.user_id] || 'Unknown User'}</span> {formatCurrency(balance.balance)}</span> :
                    balance.balance < 0 ?
                        <span><span className="font-semibold">{usersMap[balance.user.user_id] || 'Unknown User'}</span> owes you {formatCurrency(Math.abs(balance.balance))}</span> :
                        <span>You are settled with <span className="font-semibold">{usersMap[balance.user.user_id] || 'Unknown User'}</span>.</span>
                    }
                </li>
                ))}
            </ul>
            )}
            {allUserBalances && allUserBalances.length === 0 && !isLoadingAllUserBalances && (
                <p className="text-center text-gray-500 py-4">No other members in this group to compare balances with.</p>
            )}
          </div>
        )}
        {activeTab === 'settlements' && (
          <div className="p-4 bg-white rounded-lg shadow-inner">
            <h3 className="text-lg font-semibold text-gray-800 mb-3">Settle Up Suggestions</h3>
            {isLoadingSettlements && <p className="text-center text-gray-500 py-4">Calculating settlements...</p>}
            {errorSettlements && <p className="text-center text-red-500 py-4">{errorSettlements}</p>}
            {suggestedPayments && suggestedPayments.length > 0 ? (
            <ul className="space-y-3">
                {suggestedPayments.map((payment, index) => {
                    const isPayer = payment.payer.user_id === currentUser.user_id;
                    const isPayee = payment.payee.user_id === currentUser.user_id;
                    
                    let bgColor = 'bg-gray-100';
                    let textColor = 'text-gray-700';
                    let borderColor = 'border-gray-200';
                    let amountBg = 'bg-gray-200';
                    let amountText = 'text-gray-800';

                    if (isPayer) {
                        bgColor = 'bg-red-100';
                        textColor = 'text-red-700';
                        borderColor = 'border-red-200';
                        amountBg = 'bg-red-200';
                        amountText = 'text-red-800';
                    } else if (isPayee) {
                        bgColor = 'bg-green-100';
                        textColor = 'text-green-700';
                        borderColor = 'border-green-200';
                        amountBg = 'bg-green-200';
                        amountText = 'text-green-800';
                    }

                    return (
                        <li key={index} className={`p-3 rounded-lg border ${bgColor} ${borderColor}`}>
                            <div className="flex items-center justify-between text-sm sm:text-base">
                                <div className={`flex items-center space-x-2 ${textColor}`}>
                                    <span className={isPayer ? 'font-semibold' : ''}>{usersMap[payment.payer.user_id] || 'Unknown User'}</span>
                                    <span className="text-gray-500">&rarr;</span>
                                    <span className={isPayee ? 'font-semibold' : ''}>{usersMap[payment.payee.user_id] || 'Unknown User'}</span>
                                </div>
                                <span className={`font-bold px-2 py-1 rounded-md ${amountBg} ${amountText}`}>
                                    {formatCurrency(payment.amount)}
                                </span>
                            </div>
                        </li>
                    );
                })}
            </ul>
            ) : (
            !isLoadingSettlements && suggestedPayments && <p className="text-center text-gray-500 py-4">No payments are needed. Everyone is settled up!</p>
            )}
          </div>
        )}
      </div>

      {/* Section 1: Display list of bills - NOW UNDER TABS */}
      <div id="group-bills-content" className="mt-8"> {/* Added mt-8 for spacing */}
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-xl font-medium text-gray-800">Bill History</h3>
          <Link href={`/groups/${groupId}/bills/create`} passHref>
            <span className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-6 rounded-lg shadow-md hover:shadow-lg transition-all duration-150 ease-in-out cursor-pointer">
                Add New Bill
            </span>
          </Link>
        </div>
        <div className="space-y-4">
          {currentBillsToDisplay.map((bill) => {
            if (!bill) return null;
            const createdBy = bill.bill_creator?.username || bill.bill_creator?.full_name || 'Unknown User';
            
            return (
              <div
                key={bill.bill_id}
                className="p-4 border rounded-lg shadow-sm hover:shadow-md transition-shadow cursor-pointer bg-white flex justify-between items-center relative"
                onClick={() => handleBillClick(bill)}
              >
                {canDeleteBill(bill) && (
                  <button
                    onClick={(e) => handleDeleteClick(e, bill)}
                    className="absolute top-2 right-2 p-1 text-gray-400 hover:text-red-500 transition-colors"
                    title="Delete bill"
                  >
                    <XMarkIcon className="h-5 w-5" />
                  </button>
                )}
                <div className="flex-grow">
                  <h4 className="text-lg font-semibold text-gray-900 mb-0.5">{bill.title || 'Untitled Bill'}</h4>
                  <p className="text-sm text-gray-700">Created by: {createdBy}</p>
                  <p className="text-sm text-gray-700">Date: {bill.created_at ? formatDate(bill.created_at) : 'Date N/A'}</p>
                  {bill.description && (
                    <p className="text-xs text-gray-500 mt-1 italic">{`"${bill.description}"`}</p>
                  )}
                </div>
                <div className="ml-4 text-right">
                  <p className="text-lg font-semibold text-gray-900">{formatCurrency(bill.total_amount)}</p>
                  <p className="text-sm text-gray-500">{bill.split_method}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Pagination Controls for bills - This section is now always visible */}
      <div className="mt-8 flex justify-center items-center space-x-3">
        <button 
          onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
          disabled={currentPage === 1}
          className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
        >
          Previous
        </button>
        <span className="text-sm text-gray-700">
          Page {currentPage}
        </span>
        <button 
          onClick={() => setCurrentPage(prev => prev + 1)}
          disabled={!hasMoreBills}
          className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
        >
          Next
        </button>
      </div>

      {selectedBill && (
        <BillInfoModal
          bill={selectedBill}
          isOpen={!!selectedBill}
          onClose={handleCloseModal}
        />
      )}

      {/* Delete Confirmation Modal */}
      <Transition.Root show={isDeleteModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCancelDelete}>
          <div className="fixed inset-0 bg-gray-900/60 backdrop-blur-sm" />

          <div className="fixed inset-0 z-10 w-screen overflow-y-auto">
            <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
                enterTo="opacity-100 translate-y-0 sm:scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 translate-y-0 sm:scale-100"
                leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              >
                <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6">
                  <div>
                    <div className="mt-3 text-center sm:mt-5">
                      <Dialog.Title as="h3" className="text-base font-semibold leading-6 text-gray-900">
                        Delete Bill
                      </Dialog.Title>
                      <div className="mt-2">
                        <p className="text-sm text-gray-500">
                          Are you sure you want to delete this bill? This action cannot be undone.
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-5 sm:mt-6 sm:grid sm:grid-flow-row-dense sm:grid-cols-2 sm:gap-3">
                    <button
                      type="button"
                      className="inline-flex w-full justify-center rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500 sm:col-start-2"
                      onClick={handleConfirmDelete}
                      disabled={isDeleting}
                    >
                      {isDeleting ? 'Deleting...' : 'Delete'}
                    </button>
                    <button
                      type="button"
                      className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:col-start-1 sm:mt-0"
                      onClick={handleCancelDelete}
                      disabled={isDeleting}
                    >
                      Cancel
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition.Root>
    </div>
  );
};

export default GroupBills;