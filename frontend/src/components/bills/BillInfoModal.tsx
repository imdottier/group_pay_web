'use client';

import { Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { formatCurrency } from '@/lib/utils';
import { User, Bill } from '@/types';

// --- Local Type Definitions ---
interface BillPart {
  user: User;
  amount_owed: string;
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

interface BillInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  bill: Bill | null;
  isSubmitting: boolean;
}

const BillInfoModal = ({ isOpen, onClose, onConfirm, bill, isSubmitting }: BillInfoModalProps) => {
  if (!bill) return null;

  const getUserDisplayName = (user: User) => {
    return user.username || user.full_name;
  };

  const renderSplitDetails = () => {
    switch (bill.split_method) {
      case 'equal':
        const numParts = bill.bill_parts.length;
        if (numParts === 0) return <p className="text-gray-800">Split equally among all members.</p>;
        const perPerson = bill.total_amount / numParts;
        return (
          <ul className="space-y-2">
            {bill.bill_parts.map((part: BillPart) => (
              <li key={part.user.user_id} className="flex justify-between items-center">
                <span>{getUserDisplayName(part.user)}</span>
                <span className="font-medium">{formatCurrency(parseFloat(part.amount_owed))}</span>
              </li>
            ))}
          </ul>
        );
      case 'exact':
        return (
          <ul className="space-y-2">
            {bill.bill_parts.map((part: BillPart) => (
              <li key={part.user.user_id} className="flex justify-between items-center">
                <span>{getUserDisplayName(part.user)}</span>
                <span className="font-medium">{formatCurrency(parseFloat(part.amount_owed))}</span>
              </li>
            ))}
          </ul>
        );
      case 'item':
        return (
          <div className="space-y-3">
            {bill.items.map((item: BillItem) => (
              <div key={item.item_id} className="p-3 bg-gray-50 rounded-md border border-gray-200">
                <div className="flex justify-between items-center font-semibold text-gray-800">
                  <span>{item.name} <span className="text-xs font-normal text-gray-700">({item.quantity}x)</span></span>
                  <span>{formatCurrency(item.unit_price * item.quantity)}</span>
                </div>
                <ul className="mt-2 pl-4 text-sm text-gray-800 space-y-1">
                  {item.bill_item_splits.map((split: BillItemSplit) => (
                    <li key={split.user.user_id}>
                      - {getUserDisplayName(split.user)} took {split.quantity}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        );
      default:
        return <p className="text-gray-800">Split details are not available.</p>;
    }
  };
  
  return (
    <Transition.Root show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 z-10 w-screen overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-2xl transition-all sm:my-8 sm:w-full sm:max-w-md">
                <div className="bg-gray-50 px-4 py-4 sm:px-6">
                    <div>
                        <Dialog.Title as="h3" className="text-lg font-semibold leading-6 text-gray-900">
                           Confirm Bill: {bill.title}
                        </Dialog.Title>
                        {bill.description && <p className="mt-1 text-sm text-gray-800">{bill.description}</p>}
                    </div>
                </div>

                <div className="p-4 sm:p-6 space-y-6">
                    {/* -- Main Details -- */}
                    <div className="grid grid-cols-3 gap-4 text-sm">
                        <div className="col-span-1 text-gray-800">Total Amount</div>
                        <div className="col-span-2 font-semibold text-gray-900 text-right text-base">{formatCurrency(bill.total_amount)}</div>

                        <div className="col-span-1 text-gray-800">Created by</div>
                        <div className="col-span-2 font-medium text-gray-800 text-right">{bill.bill_creator?.username || bill.bill_creator?.full_name || 'Unknown'}</div>
                        
                        <div className="col-span-1 text-gray-800">Date</div>
                        <div className="col-span-2 font-medium text-gray-800 text-right">{new Date(bill.created_at).toLocaleDateString()}</div>
                    </div>
                    
                    {/* -- Sections -- */}
                    <div className="space-y-4">
                        {bill.initial_payments.length > 0 && (
                            <div className="border-t border-gray-200 pt-4">
                                <h4 className="font-semibold text-gray-800 mb-2">Paid By</h4>
                                <ul className="space-y-2 text-sm">
                                    {bill.initial_payments.map((p: InitialPayment, index: number) => (
                                        <li key={`${p.user.user_id}-${index}`} className="flex justify-between items-center">
                                            <span className="font-medium text-gray-900">{getUserDisplayName(p.user)}</span>
                                            <span className="font-medium text-gray-900">{formatCurrency(parseFloat(p.amount_paid))}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        
                        <div className="border-t border-gray-200 pt-4">
                            <h4 className="font-semibold text-gray-800 mb-2">Split Details</h4>
                            <div className="text-sm text-gray-900">
                                {renderSplitDetails()}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
                  <button
                    type="button"
                    className="inline-flex w-full justify-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 sm:ml-3 sm:w-auto disabled:bg-indigo-400"
                    onClick={onConfirm}
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? 'Confirming...' : 'Confirm'}
                  </button>
                  <button
                    type="button"
                    className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:mt-0 sm:w-auto"
                    onClick={onClose}
                    disabled={isSubmitting}
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
  );
};

export default BillInfoModal; 