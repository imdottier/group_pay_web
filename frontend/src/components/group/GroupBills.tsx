'use client';

import React, { useState, useMemo, Fragment } from 'react';
import useSWR, { mutate, BareFetcher } from 'swr';
import api from '@/lib/api';
import Link from 'next/link';
import { formatCurrency, roundToNearest500, get_user_role } from '@/lib/utils';
import BillInfoModal from '@/components/bills/BillInfoModal';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { Dialog, Transition } from '@headlessui/react';
import { User, Bill } from '@/types';

// --- INTERFACES ---
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
interface UserNetBalance {
  user_id: number;
  username: string;
  net_amount: number;
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
interface SettlementSummary {
  suggested_payments: SettlementTransaction[];
}
interface GroupBillsProps {
  groupId: string;
  currentUser: any;
  onPaymentCreated: () => void;
}
interface Member {
  user: User;
  role: string;
}

// --- GLOBAL HELPERS ---
const fetcher: BareFetcher<any> = (url: string) => api.get(url).then(res => res.data);

const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
  });
};

// --- COMPONENT ---
export const GroupBills: React.FC<GroupBillsProps> = ({ groupId, currentUser, onPaymentCreated }) => {
  // 1. LOCAL UI STATE
  const [currentPage, setCurrentPage] = useState(1);
  const [activeTab, setActiveTab] = useState<'overall_balances' | 'balance_with_user' | 'settlements'>('overall_balances');
  const [selectedBill, setSelectedBill] = useState<Bill | null>(null);
  const [billToDelete, setBillToDelete] = useState<Bill | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSettling, setIsSettling] = useState<number | null>(null);
  const billsPerPage = 10;

  // 2. SWR DATA FETCHING
  const membersApiUrl = groupId ? `/groups/${groupId}/members` : null;
  const { data: members, error: errorMembers } = useSWR<Member[]>(membersApiUrl, fetcher);

  const billsApiUrl = groupId ? `/groups/${groupId}/bills/?skip=${(currentPage - 1) * billsPerPage}&limit=${billsPerPage}` : null;
  const { data: bills, error: errorBills, isLoading: isLoadingBills } = useSWR<Bill[]>(billsApiUrl, fetcher);

  const balancesApiUrl = groupId && activeTab === 'overall_balances' ? `/groups/${groupId}/balances` : null;
  const { data: netBalancesData, error: errorBalances, isLoading: isLoadingBalances } = useSWR<GroupBalanceSummary>(balancesApiUrl, fetcher);
  
  const allUserBalancesApiUrl = groupId && activeTab === 'balance_with_user' ? `/groups/${groupId}/balances_with_all_members` : null;
  const { data: allUserBalances, error: errorAllUserBalances, isLoading: isLoadingAllUserBalances } = useSWR<SimpleUserBalance[]>(allUserBalancesApiUrl, fetcher);
  
  const settlementsApiUrl = groupId && activeTab === 'settlements' ? `/groups/${groupId}/settlements` : null;
  const { data: settlementsData, error: errorSettlements, isLoading: isLoadingSettlements } = useSWR<SettlementSummary>(settlementsApiUrl, fetcher);

  // 3. MEMOIZED/DERIVED STATE
  const usersMap = useMemo(() => {
    if (!members) return {};
    return members.reduce((acc: Record<number, string>, member) => {
      acc[member.user.user_id] = member.user.username || member.user.full_name || 'Unknown';
      return acc;
    }, {});
  }, [members]);

  const userRole = useMemo(() => {
    if (!currentUser || !members) return null;
    const currentUserMember = members.find(m => m.user.user_id === currentUser.user_id);
    return currentUserMember ? currentUserMember.role : null;
  }, [currentUser, members]);

  const suggestedPayments = useMemo(() => {
    if (!settlementsData?.suggested_payments) return [];
    return settlementsData.suggested_payments.map(p => ({ ...p, amount: roundToNearest500(p.amount) }));
  }, [settlementsData]);

  const hasMoreBills = (bills?.length ?? 0) === billsPerPage;

  // 4. EVENT HANDLERS
  const handleBillClick = (bill: Bill) => setSelectedBill(bill);
  const handleCloseModal = () => setSelectedBill(null);

  const handleDeleteClick = (e: React.MouseEvent, bill: Bill) => {
    e.stopPropagation();
    setBillToDelete(bill);
    setIsDeleteModalOpen(true);
  };

  const handleCancelDelete = () => {
    setIsDeleteModalOpen(false);
    setBillToDelete(null);
  };

  const handleSettlePayment = async (payment: SettlementTransaction, index: number) => {
    setIsSettling(index);
    try {
      await api.post('/payments/', {
        group_id: groupId,
        payee_id: payment.payee.user_id,
        amount: payment.amount,
        notes: `Settlement from ${payment.payer.username} to ${payment.payee.username}`
      });
      
      // Revalidate data
      mutate(settlementsApiUrl);
      mutate(balancesApiUrl);
      mutate(allUserBalancesApiUrl);
      // We also need to revalidate the main payments list, but we'll do that in the parent
      
      onPaymentCreated(); // Switch to the payments tab

    } catch (error) {
      console.error("Failed to settle payment:", error);
      // toast.error("Failed to settle payment.");
    } finally {
      setIsSettling(null);
    }
  };

  const handleConfirmDelete = async () => {
    if (!billToDelete || !billsApiUrl) return;
    setIsDeleting(true);
    try {
      await api.delete(`/groups/${groupId}/bills/${billToDelete.bill_id}`);
      mutate(billsApiUrl); // Revalidate the bills list
      handleCancelDelete();
    } catch (error) {
      console.error("Failed to delete bill:", error);
      // Consider adding a toast notification for the user here
    } finally {
      setIsDeleting(false);
    }
  };
  
  const canDeleteBill = (bill: Bill) => {
    if (!currentUser || !userRole) return false;
    return bill.created_by === currentUser.user_id || userRole === 'admin' || userRole === 'owner';
  };

  // 5. RENDER LOGIC
  if (!currentUser) return <div className="p-4 text-center">Loading user data...</div>;
  if (errorMembers) return <div className="p-4 text-center text-red-500">Error loading group members. Please refresh the page.</div>;

  return (
    <div className="w-full">
      {/* TABS */}
      <div className="mt-8">
        <div className="mb-6 flex justify-around items-center p-1 bg-gray-200/70 rounded-lg shadow-inner">
          <button onClick={() => setActiveTab('overall_balances')} className={`flex-1 py-2.5 px-4 text-sm font-medium rounded-lg transition-all duration-200 ${activeTab === 'overall_balances' ? 'bg-white text-black shadow' : 'text-black hover:bg-white/60'}`}>Overall Balances</button>
          <button onClick={() => setActiveTab('balance_with_user')} className={`flex-1 py-2.5 px-4 text-sm font-medium rounded-lg transition-all duration-200 ${activeTab === 'balance_with_user' ? 'bg-white text-black shadow' : 'text-black hover:bg-white/60'}`}>My Balances with Others</button>
          <button onClick={() => setActiveTab('settlements')} className={`flex-1 py-2.5 px-4 text-sm font-medium rounded-lg transition-all duration-200 ${activeTab === 'settlements' ? 'bg-white text-black shadow' : 'text-black hover:bg-white/60'}`}>Settle Up</button>
        </div>
      
        {/* TAB CONTENT */}
        {activeTab === 'overall_balances' && (
          <div className="p-4 bg-white rounded-lg shadow-inner">
            <h3 className="text-lg font-semibold text-gray-800 mb-3">Overall Group Balances</h3>
            {isLoadingBalances && <p className="text-center text-gray-500 py-4">Loading balances...</p>}
            {errorBalances && <p className="text-center text-red-500 py-4">Failed to load overall balances.</p>}
            {netBalancesData?.balances && netBalancesData.balances.length > 0 && (
                <ul className="space-y-2">
                    {netBalancesData.balances.map(balance => (
                        <li key={balance.user_id} className={`py-3 px-4 flex justify-between items-center rounded-lg shadow-sm text-sm sm:text-base ${balance.net_amount > 0 ? 'bg-red-100 text-red-700' : balance.net_amount < 0 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                            <span className="font-medium">{usersMap[balance.user_id] ?? 'Unknown User'}</span>
                            <span className="font-semibold">
                                {balance.net_amount > 0 && `Owes ${formatCurrency(balance.net_amount)}`}
                                {balance.net_amount < 0 && `Owed ${formatCurrency(Math.abs(balance.net_amount))}`}
                                {balance.net_amount === 0 && 'Settled up'}
                            </span>
                        </li>
                    ))}
                </ul>
            )}
            {!isLoadingBalances && !errorBalances && netBalancesData?.balances?.length === 0 && (
                <p className="text-center text-gray-500 py-4">No balances to display for this group.</p>
            )}
          </div>
        )}
        {activeTab === 'balance_with_user' && (
          <div className="p-4 bg-white rounded-lg shadow-inner">
            <h3 className="text-lg font-semibold text-gray-800 mb-3">Your Balances with Other Members</h3>
            {isLoadingAllUserBalances && <p className="text-center py-4">Loading balances with other users...</p>}
            {errorAllUserBalances && <p className="text-center text-red-500 py-4">Failed to load balances with other users.</p>}
            {allUserBalances && allUserBalances.length > 0 && (
            <ul className="space-y-2">
                {allUserBalances.map((balance) => (
                <li key={balance.user.user_id} className={`p-3 rounded-md text-sm ${balance.balance > 0 ? 'bg-red-100 text-red-700' : balance.balance < 0 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                    {balance.balance > 0 ? <span>You owe <span className="font-semibold">{usersMap[balance.user.user_id] ?? 'Unknown User'}</span> {formatCurrency(balance.balance)}</span> :
                    balance.balance < 0 ? <span><span className="font-semibold">{usersMap[balance.user.user_id] ?? 'Unknown User'}</span> owes you {formatCurrency(Math.abs(balance.balance))}</span> :
                        <span>You are settled with <span className="font-semibold">{usersMap[balance.user.user_id] ?? 'Unknown User'}</span>.</span>}
                </li>
                ))}
            </ul>
            )}
            {!isLoadingAllUserBalances && allUserBalances?.length === 0 && ( <p className="text-center text-gray-500 py-4">No other members in this group to compare balances with.</p>)}
          </div>
        )}
        {activeTab === 'settlements' && (
          <div className="p-4 bg-white rounded-lg shadow-inner">
            <h3 className="text-lg font-semibold text-gray-800 mb-3">Settle Up Suggestions</h3>
            {isLoadingSettlements && <p className="text-center text-gray-500 py-4">Calculating settlements...</p>}
            {errorSettlements && <p className="text-center text-red-500 py-4">Failed to calculate settlements.</p>}
            {suggestedPayments && suggestedPayments.length > 0 ? (
            <ul className="space-y-3">
                {suggestedPayments.map((payment, index) => {
                    const isPayer = payment.payer.user_id === currentUser.user_id;
                    const isPayee = payment.payee.user_id === currentUser.user_id;
                    let bgColor = isPayer ? 'bg-red-100' : isPayee ? 'bg-green-100' : 'bg-gray-100';
                    let textColor = isPayer ? 'text-red-700' : isPayee ? 'text-green-700' : 'text-gray-700';
                    let borderColor = isPayer ? 'border-red-200' : isPayee ? 'border-green-200' : 'border-gray-200';
                    let amountBg = isPayer ? 'bg-red-200' : isPayee ? 'bg-green-200' : 'bg-gray-200';
                    let amountText = isPayer ? 'text-red-800' : isPayee ? 'text-green-800' : 'text-gray-800';

                    return (
                        <li key={index} className={`p-3 rounded-lg border ${bgColor} ${borderColor} flex items-center justify-between`}>
                            <div className="flex items-center justify-between text-sm sm:text-base flex-grow">
                                <div className={`flex items-center space-x-2 ${textColor}`}>
                                    <span className={isPayer ? 'font-semibold' : ''}>{usersMap[payment.payer.user_id] ?? 'Unknown User'}</span>
                                    <span className="text-gray-500">&rarr;</span>
                                    <span className={isPayee ? 'font-semibold' : ''}>{usersMap[payment.payee.user_id] ?? 'Unknown User'}</span>
                                </div>
                                <span className={`font-bold px-2 py-1 rounded-md ${amountBg} ${amountText}`}>{formatCurrency(payment.amount)}</span>
                            </div>
                            {isPayer && (
                              <button
                                onClick={() => handleSettlePayment(payment, index)}
                                disabled={isSettling === index}
                                className="ml-4 bg-green-600 text-white font-semibold py-1 px-3 rounded-md hover:bg-green-700 transition ease-in-out duration-150 disabled:bg-gray-400"
                              >
                                {isSettling === index ? 'Settling...' : 'Settle'}
                              </button>
                            )}
                        </li>
                    );
                })}
            </ul>
            ) : (!isLoadingSettlements && <p className="text-center text-gray-500 py-4">No payments are needed. Everyone is settled up!</p>)}
          </div>
        )}
      </div>

      {/* BILLS LIST */}
      <div id="group-bills-content" className="mt-8">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-xl font-medium text-gray-800">Bill History</h3>
          <Link href={`/groups/${groupId}/bills/create`} passHref>
            <span className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-6 rounded-lg shadow-md hover:shadow-lg transition-all duration-150 ease-in-out cursor-pointer">Add New Bill</span>
          </Link>
        </div>
        {isLoadingBills && <div className="text-center p-4">Loading bills...</div>}
        {errorBills && <div className="text-center p-4 text-red-500">Failed to load bills.</div>}
        <div className="space-y-4">
          {bills?.map((bill) => {
            if (!bill) return null;
            const createdBy = usersMap[bill.created_by] ?? 'Unknown User';
            return (
              <div key={bill.bill_id} className="p-4 border rounded-lg shadow-sm hover:shadow-md transition-shadow cursor-pointer bg-white flex justify-between items-center relative" onClick={() => handleBillClick(bill)}>
                {canDeleteBill(bill) && (
                  <button onClick={(e) => handleDeleteClick(e, bill)} className="absolute top-2 right-2 p-1 text-gray-400 hover:text-red-500 transition-colors" title="Delete bill">
                    <XMarkIcon className="h-5 w-5" />
                  </button>
                )}
                <div className="flex-grow">
                  <h4 className="text-lg font-semibold text-gray-900 mb-0.5">{bill.title || 'Untitled Bill'}</h4>
                  <p className="text-sm text-gray-700">Created by: {createdBy}</p>
                  <p className="text-sm text-gray-700">Date: {bill.created_at ? formatDate(bill.created_at) : 'Date N/A'}</p>
                  {bill.description && (<p className="text-xs text-gray-500 mt-1 italic">{`"${bill.description}"`}</p>)}
                </div>
                <div className="ml-4 text-right">
                  <p className="text-lg font-semibold text-gray-900">{formatCurrency(bill.total_amount)}</p>
                  <p className="text-sm text-gray-500">{bill.split_method}</p>
                </div>
              </div>
            );
          })}
        </div>
        {!isLoadingBills && bills?.length === 0 && (
          <div className="text-center p-8 border-2 border-dashed rounded-lg mt-4">
            <h3 className="text-lg font-medium text-gray-900">No bills yet</h3>
            <p className="mt-1 text-sm text-gray-500">Get started by adding a new bill.</p>
          </div>
        )}
      </div>

      {/* PAGINATION */}
      <div className="mt-8 flex justify-center items-center space-x-3">
        <button onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))} disabled={currentPage === 1 || isLoadingBills} className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium">Previous</button>
        <span className="text-sm text-gray-700">Page {currentPage}</span>
        <button onClick={() => setCurrentPage(prev => prev + 1)} disabled={!hasMoreBills || isLoadingBills} className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium">Next</button>
      </div>

      {/* MODALS */}
      {selectedBill && ( <BillInfoModal bill={selectedBill} isOpen={!!selectedBill} onClose={handleCloseModal} onConfirm={() => {}} isSubmitting={false} /> )}

      <Transition.Root show={isDeleteModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCancelDelete}>
          <div className="fixed inset-0 bg-gray-900/60 backdrop-blur-sm" />
          <div className="fixed inset-0 z-10 w-screen overflow-y-auto">
            <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
              <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95" enterTo="opacity-100 translate-y-0 sm:scale-100" leave="ease-in duration-200" leaveFrom="opacity-100 translate-y-0 sm:scale-100" leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95">
                <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6">
                  <div>
                    <div className="mt-3 text-center sm:mt-5">
                      <Dialog.Title as="h3" className="text-base font-semibold leading-6 text-gray-900">Delete Bill</Dialog.Title>
                      <div className="mt-2"><p className="text-sm text-gray-500">Are you sure you want to delete this bill? This action cannot be undone.</p></div>
                    </div>
                  </div>
                  <div className="mt-5 sm:mt-6 sm:grid sm:grid-flow-row-dense sm:grid-cols-2 sm:gap-3">
                    <button type="button" className="inline-flex w-full justify-center rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500 sm:col-start-2" onClick={handleConfirmDelete} disabled={isDeleting}>{isDeleting ? 'Deleting...' : 'Delete'}</button>
                    <button type="button" className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:col-start-1 sm:mt-0" onClick={handleCancelDelete} disabled={isDeleting}>Cancel</button>
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