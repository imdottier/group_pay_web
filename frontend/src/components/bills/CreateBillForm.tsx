'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { User, GroupMember, InitialPayer, Bill, BillPart, BillItemSplit, BillItem } from '@/types';
import BillInfoModal from './BillInfoModal';
import { formatCurrency } from '@/lib/utils';
import { XMarkIcon, CameraIcon } from '@heroicons/react/24/outline';
import { toast } from 'sonner';

type SplitMethod = 'equal' | 'exact' | 'item';

interface BillCategory {
    category_id: number;
    name: string;
}

interface ItemAssignment {
  user_id: number;
  quantity: number;
}

interface ExactSplit {
  user_id: number;
  amount_owed: number;
}

interface ParsedItemData {
  name: string;
  quantity: number;
  unit_price: number;
}

interface ParsedReceiptData {
  store_name?: string;
  total_amount: number;
  items: ParsedItemData[];
}

interface CreateBillFormProps {
  groupId: string;
}

// Add a local interface for editable bill items
interface EditableBillItem {
  id: number;
  name: string;
  unit_price: number;
  quantity: number;
  assignments: ItemAssignment[];
}

const CreateBillForm = ({ groupId }: CreateBillFormProps) => {
  const router = useRouter();
  const [groupMembers, setGroupMembers] = useState<GroupMember[]>([]);
  const [billCategories, setBillCategories] = useState<BillCategory[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isConfirmationModalOpen, setIsConfirmationModalOpen] = useState(false);

  // --- Receipt Parsing State ---
  const [receiptFile, setReceiptFile] = useState<File | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [parsingError, setParsingError] = useState<string | null>(null);

  // --- Form State ---
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [totalAmount, setTotalAmount] = useState<string>('');
  const [splitMethod, setSplitMethod] = useState<SplitMethod>('equal');
  const [categoryMode, setCategoryMode] = useState<'existing' | 'new'>('existing');
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>('');
  const [newCategoryName, setNewCategoryName] = useState('');

  const [initialPayers, setInitialPayers] = useState<InitialPayer[]>([{ user_id: 0, amount_paid: '' as any }]);
  const [items, setItems] = useState<EditableBillItem[]>([
    { id: Date.now(), name: '', unit_price: 0, quantity: 1, assignments: [] }
  ]);
  const [exactSplits, setExactSplits] = useState<ExactSplit[]>([]);
  const [splitParticipants, setSplitParticipants] = useState<number[]>([]);

  useEffect(() => {
    const fetchPrerequisites = async () => {
      try {
        const [membersResponse, categoriesResponse] = await Promise.all([
          api.get<GroupMember[]>(`/groups/${groupId}/members`),
          api.get<BillCategory[]>(`/bill_categories/group/${groupId}`)
        ]);
        
        const members = membersResponse.data;
        setGroupMembers(members);

        const categories = categoriesResponse.data;
        setBillCategories(categories);
        if (categories.length > 0) {
          setSelectedCategoryId(categories[0].category_id.toString());
        }

        if (members.length > 0) {
          setInitialPayers([{ user_id: members[0].user.user_id, amount_paid: '' as any }]);
          setSplitParticipants(members.map(m => m.user.user_id));
          setExactSplits(members.map(m => ({ user_id: m.user.user_id, amount_owed: 0 })));
          const initialAssignments = members.map(m => ({ user_id: m.user.user_id, quantity: 0 }));
          setItems(prevItems => prevItems.map(item => ({...item, assignments: initialAssignments})));
        }
      } catch (err) {
        setError('Failed to load group members or categories. Please try again.');
        console.error(err);
      }
    };
    fetchPrerequisites();
  }, [groupId]);

  const handleReceiptParse = async () => {
    if (!receiptFile) {
      setParsingError("Please select an image file first.");
      return;
    }

    setParsingError(null);
    setIsParsing(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", receiptFile);

    try {
      const response = await api.post<ParsedReceiptData>(`/receipt-parser/parse-receipt`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const { store_name, total_amount, items: parsedItems } = response.data;
      
      // Update form state with parsed data
      if (store_name) {
        setTitle(store_name);
      }
      setTotalAmount(total_amount.toString());
      
      if (parsedItems && parsedItems.length > 0) {
        const newItems = parsedItems.map((item: ParsedItemData) => ({
          id: Date.now() + Math.random(),
          name: item.name,
          unit_price: item.unit_price,
          quantity: item.quantity,
          assignments: groupMembers.map(m => ({ user_id: m.user.user_id, quantity: 0 }))
        }));
        setItems(newItems);
        // Automatically set split method to 'item' if items are found
        setSplitMethod('item');
        toast.success(`Successfully parsed ${parsedItems.length} items from the receipt.`);
      } else {
        toast.info("Could not find distinct items, but updated the total amount.");
      }

    } catch (err: any) {
      console.error("Receipt parsing failed:", err);
      const detail = err.response?.data?.detail || "An unknown error occurred during parsing.";
      setParsingError(`Failed to parse receipt: ${detail}`);
      toast.error("Receipt parsing failed.");
    } finally {
      setIsParsing(false);
    }
  };

  const handleAddItem = () => {
    const newAssignments = groupMembers.map(m => ({ user_id: m.user.user_id, quantity: 0 }));
    setItems([...items, { id: Date.now(), name: '', unit_price: 0, quantity: 1, assignments: newAssignments }]);
  };

  const handleItemChange = (index: number, field: keyof Omit<EditableBillItem, 'id' | 'assignments'>, value: string) => {
    const updatedItems = [...items];
    const item = { ...updatedItems[index] };
    if (field === 'name') {
        item[field] = value;
    } else {
        item[field] = value as any;
    }
    updatedItems[index] = item;
    setItems(updatedItems);
  };
  
  const handleRemoveItem = (index: number) => {
    setItems(items.filter((_, i) => i !== index));
  };

  const handleItemAssignmentChange = (itemIndex: number, userId: number, quantity: string) => {
    const newQuantity = Number(quantity);
    if (isNaN(newQuantity) || newQuantity < 0) return;
    const updatedItems = [...items];
    const item = { ...updatedItems[itemIndex] };
    const existingAssignmentIndex = item.assignments.findIndex(a => a.user_id === userId);
    if (existingAssignmentIndex > -1) {
        item.assignments[existingAssignmentIndex].quantity = newQuantity;
    } else {
        item.assignments.push({ user_id: userId, quantity: newQuantity });
    }
    updatedItems[itemIndex] = item;
    setItems(updatedItems);
  };

  const getAssignedQuantityForItem = (itemIndex: number) => items[itemIndex].assignments.reduce((sum, a) => sum + a.quantity, 0);

  const handleAddPayer = () => {
    const availableMember = groupMembers.find(gm => !initialPayers.some(p => p.user_id === gm.user.user_id));
    if (availableMember) {
      setInitialPayers([...initialPayers, { user_id: availableMember.user.user_id, amount_paid: '' as any }]);
    }
  };

  const handlePayerChange = (index: number, field: keyof InitialPayer, value: any) => {
    const updatedPayers = [...initialPayers];
    updatedPayers[index] = { ...updatedPayers[index], [field]: value };
    setInitialPayers(updatedPayers);
  };

  const handleRemovePayer = (index: number) => {
    setInitialPayers(initialPayers.filter((_, i) => i !== index));
  };
  
  const currentTotalPaid = useMemo(() => initialPayers.reduce((sum, p) => sum + Number(p.amount_paid || 0), 0), [initialPayers]);
  const totalAmountNumber = useMemo(() => Number(totalAmount || 0), [totalAmount]);
  const remainingAmount = useMemo(() => totalAmountNumber - currentTotalPaid, [totalAmountNumber, currentTotalPaid]);

  const handleParticipantChange = (userId: number) => {
    setSplitParticipants(prev => prev.includes(userId) ? prev.filter(id => id !== userId) : [...prev, userId]);
  };

  const handleSelectAllParticipants = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSplitParticipants(event.target.checked ? groupMembers.map(m => m.user.user_id) : []);
  };

  const handleAmountChange = (userId: number, value: string) => {
    const amount = Number(value);
    const newSplits = exactSplits.map(split =>
        split.user_id === userId ? { ...split, amount_owed: isNaN(amount) ? 0 : amount } : split
    );
    setExactSplits(newSplits);
  };

  const totalSplitAmount = useMemo(() => exactSplits.reduce((sum, split) => sum + (split.amount_owed || 0), 0), [exactSplits]);

  const itemizedTotalAmount = useMemo(() => {
    return items.reduce((sum, item) => sum + (Number(item.unit_price) || 0) * (Number(item.quantity) || 0), 0);
  }, [items]);

  useEffect(() => {
    // If there are items, the total amount is determined by them.
    if (itemizedTotalAmount > 0) {
      setTotalAmount(itemizedTotalAmount.toString());
    }
  }, [itemizedTotalAmount]);

  const equalSplitAmount = useMemo(() => {
    if (splitParticipants.length === 0 || totalAmountNumber === 0) return 0;
    return totalAmountNumber / splitParticipants.length;
  }, [splitParticipants.length, totalAmountNumber]);

  const getConfirmationBill = (): Bill | null => {
    const validInitialPayers = initialPayers.filter(p => p.amount_paid && Number(p.amount_paid) > 0);
    
    let billParts: BillPart[] = [];
    if (splitMethod === 'exact') {
      billParts = exactSplits.filter(s => s.amount_owed > 0).map(split => ({
        user: groupMembers.find(m => m.user.user_id === split.user_id)?.user,
        amount_owed: split.amount_owed.toString()
      })).filter((part): part is { user: User; amount_owed: string } => part.user !== undefined);
    } else if (splitMethod === 'equal') {
      billParts = splitParticipants.map(userId => ({
        user: groupMembers.find(m => m.user.user_id === userId)?.user,
        amount_owed: equalSplitAmount.toString()
      })).filter((part): part is { user: User; amount_owed: string } => part.user !== undefined);
    }

    const creator = groupMembers[0]?.user;
    if (!creator) return null;

    return {
      bill_id: 0,
      title,
      description: description || '',
      total_amount: totalAmountNumber,
      created_by: creator.user_id,
      bill_creator: creator,
      created_at: new Date().toISOString(),
      split_method: splitMethod,
      initial_payments: validInitialPayers.map(p => ({
        user: groupMembers.find(m => m.user.user_id === p.user_id)?.user,
        amount_paid: p.amount_paid.toString()
      })).filter((payment): payment is { user: User; amount_paid: string } => payment.user !== undefined),
      bill_parts: billParts,
      items: splitMethod === 'item' ? items.map(item => ({
        item_id: item.id,
        name: item.name,
        unit_price: item.unit_price || 0,
        quantity: item.quantity,
        bill_item_splits: item.assignments.filter(a => a.quantity > 0).map(split => ({
          user: groupMembers.find(m => m.user.user_id === split.user_id)?.user,
          quantity: split.quantity
        })).filter((split): split is { user: User; quantity: number } => split.user !== undefined)
      })) : []
    };
  };

  const handleOpenConfirmation = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // --- Validation ---
    const hasItems = items.length > 0 && items.some(i => i.name && Number(i.unit_price) > 0 && Number(i.quantity) > 0);

    if (hasItems && Math.abs(itemizedTotalAmount - totalAmountNumber) > 0.01) {
      setError("The total amount must equal the sum of the item prices.");
      return;
    }

    if (splitMethod === 'exact' && Math.abs(totalSplitAmount - totalAmountNumber) > 0.01) {
        setError("The sum of split amounts must equal the total bill amount.");
        return;
    }
    if (splitMethod === 'item') {
      if (!hasItems) {
        setError("You must add at least one item to use the 'Item' split method.");
        return;
      }
      for (const [index, item] of items.entries()) {
        const assigned = getAssignedQuantityForItem(index);
        const quantity = Number(item.quantity) || 0;
        if (assigned !== quantity) {
          setError(`For item "${item.name || `Item #${index + 1}`}", the assigned quantities (${assigned}) do not sum up to the total quantity (${quantity}).`);
          return;
        }
      }
    }
    setIsConfirmationModalOpen(true);
  };

  const handleConfirmSubmit = async () => {
    setIsLoading(true);

    const validInitialPayers = initialPayers.filter(p => p.amount_paid && Number(p.amount_paid) > 0);
    const hasItems = items.length > 0 && items.some(i => i.name && Number(i.unit_price) > 0 && Number(i.quantity) > 0);
    
    const payload: any = {
        title,
        total_amount: totalAmountNumber,
        description: description || null,
        split_method: splitMethod,
        initial_payments: validInitialPayers.map(p => ({...p, amount_paid: Number(p.amount_paid)})),
        items: [],
        bill_parts: null,
    };

    if (categoryMode === 'existing' && selectedCategoryId) {
      payload.category_input = { type: 'existing', category_id: Number(selectedCategoryId) };
    } else if (categoryMode === 'new' && newCategoryName.trim()) {
      payload.category_input = { type: 'new', name: newCategoryName.trim() };
    } else {
      payload.category_input = null;
    }

    // Always include items if they have been added
    if (hasItems) {
      payload.items = items.map(item => ({
        name: item.name,
        unit_price: item.unit_price,
        quantity: item.quantity,
        splits: item.assignments.filter(a => a.quantity > 0).map(a => ({
          user_id: a.user_id,
          quantity: a.quantity
        }))
      }));
    }

    if (splitMethod === 'exact') {
      payload.bill_parts = exactSplits.filter(s => s.amount_owed > 0);
    } else if (splitMethod === 'item') {
      // The payload.items is already populated above
    } else { // 'equal'
        const isFullGroup = splitParticipants.length === groupMembers.length;
        if (!isFullGroup) {
            // If only a subset is selected, treat it as an exact split behind the scenes
            payload.split_method = 'exact';
            payload.bill_parts = splitParticipants.map(userId => ({
                user_id: userId,
                amount_owed: equalSplitAmount
            }));
        }
    }
    
    const formData = new FormData();
    formData.append('bill_data', JSON.stringify(payload));
    if (receiptFile) {
        formData.append('receipt_image', receiptFile);
    }

    try {
      await api.post(`/groups/${groupId}/bills`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
      });
      toast.success(`Bill "${title}" created successfully!`);
      router.push(`/groups/${groupId}?tab=bills`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'An unexpected error occurred.');
      console.error(err);
      setIsConfirmationModalOpen(false); // Close modal on error to show the error message on form
    } finally {
      setIsLoading(false);
    }
  };

  const isFormInvalid = !title.trim() || totalAmountNumber <= 0 || remainingAmount < 0;

  return (
    <form onSubmit={handleOpenConfirmation} className="space-y-8">
        {/* --- Receipt Parser Section --- */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h2 className="text-xl font-semibold mb-4 text-gray-800 flex items-center">
            <CameraIcon className="h-6 w-6 mr-3 text-gray-600"/>
            Auto-fill from Receipt
          </h2>
          <div className="flex flex-col sm:flex-row sm:items-center sm:space-x-4 space-y-3 sm:space-y-0">
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setReceiptFile(e.target.files ? e.target.files[0] : null)}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
            />
            <button
              type="button"
              onClick={handleReceiptParse}
              disabled={isParsing || !receiptFile}
              className="px-5 py-2.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 focus:ring-4 focus:ring-indigo-300 disabled:bg-indigo-400 disabled:cursor-not-allowed w-full sm:w-auto"
            >
              {isParsing ? 'Scanning...' : 'Scan Receipt'}
            </button>
          </div>
          {parsingError && <p className="text-red-500 text-sm mt-3">{parsingError}</p>}
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <h2 className="text-xl font-semibold mb-4 text-gray-800">Bill Details</h2>
            <div className="space-y-4">
                <div>
                    <label htmlFor="title" className="block text-sm font-medium text-gray-900">Title</label>
                    <input type="text" id="title" value={title} onChange={(e) => setTitle(e.target.value)} required className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-700 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900" placeholder="e.g., Monthly Rent" />
                </div>
                <div>
                    <label htmlFor="description" className="block text-sm font-medium text-gray-900">Description (Optional)</label>
                    <textarea id="description" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-700 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900" placeholder="A brief note about the bill" />
                </div>

                {/* --- Category Section --- */}
                <div>
                    <label className="block text-sm font-medium text-gray-900 mb-2">Category</label>
                    <div className="flex items-center space-x-4 mb-3">
                        <label className="flex items-center"><input type="radio" name="categoryMode" value="existing" checked={categoryMode === 'existing'} onChange={() => setCategoryMode('existing')} className="form-radio h-4 w-4 text-indigo-600"/> <span className="ml-2 text-gray-900">Existing</span></label>
                        <label className="flex items-center"><input type="radio" name="categoryMode" value="new" checked={categoryMode === 'new'} onChange={() => setCategoryMode('new')} className="form-radio h-4 w-4 text-indigo-600"/> <span className="ml-2 text-gray-900">New</span></label>
                    </div>
                    {categoryMode === 'existing' ? (
                        <select id="category" value={selectedCategoryId} onChange={(e) => setSelectedCategoryId(e.target.value)} className="mt-1 block w-full pl-3 pr-10 py-2 text-base border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900" disabled={billCategories.length === 0}>
                            {billCategories.length > 0 ? billCategories.map(cat => (<option key={cat.category_id} value={cat.category_id}>{cat.name}</option>)) : (<option>No categories available</option>)}
                        </select>
                    ) : (
                        <input type="text" value={newCategoryName} onChange={(e) => setNewCategoryName(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-700 text-gray-900" placeholder="Enter new category name"/>
                    )}
                </div>

                <div>
                    <label htmlFor="totalAmount" className="block text-sm font-medium text-gray-900">Total Amount</label>
                    <input type="number" id="totalAmount" value={totalAmount} onChange={(e) => setTotalAmount(e.target.value)} required min="0" step="1" className={`mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-700 text-gray-900 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none ${itemizedTotalAmount > 0 ? 'bg-gray-100' : ''}`} placeholder="0" readOnly={itemizedTotalAmount > 0} />
                </div>
            </div>
        </div>

        {/* --- Paid By Section --- */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <h2 className="text-xl font-semibold mb-4 text-gray-800">Paid By</h2>
            <div className="space-y-4">
                {initialPayers.map((payer, index) => (
                    <div key={index} className="flex items-center space-x-3">
                        <div className="flex-1">
                            <label htmlFor={`payer-user-${index}`} className="sr-only">Payer</label>
                            <select id={`payer-user-${index}`} value={payer.user_id} onChange={(e) => handlePayerChange(index, 'user_id', Number(e.target.value))} className="block w-full pl-3 pr-10 py-2 text-base border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900">
                                {groupMembers.map(member => <option key={member.user.user_id} value={member.user.user_id}>{member.user.username || member.user.full_name}</option>)}
                            </select>
                        </div>
                        <div className="flex-1">
                            <label htmlFor={`payer-amount-${index}`} className="sr-only">Amount Paid</label>
                            <input type="number" id={`payer-amount-${index}`} value={payer.amount_paid || ''} onChange={(e) => handlePayerChange(index, 'amount_paid', e.target.value)} required min="0" step="1" className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-700 text-gray-900 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none" placeholder="0" />
                        </div>
                        {initialPayers.length > 1 && (
                            <button type="button" onClick={() => handleRemovePayer(index)} className="text-red-600 hover:text-red-800 p-1">Remove</button>
                        )}
                    </div>
                ))}
            </div>
            <div className="mt-4 flex items-center justify-between">
                <button type="button" onClick={handleAddPayer} disabled={initialPayers.length >= groupMembers.length} className="text-sm font-medium text-indigo-600 hover:text-indigo-500 disabled:opacity-50">
                    + Add another payer
                </button>
                <div className="text-sm">
                    <span className="text-gray-900">Remaining:</span>
                    <span className={`font-medium ml-2 ${remainingAmount < 0 ? 'text-red-600' : 'text-gray-900'}`}>{formatCurrency(remainingAmount, { rounding: false })}</span>
                </div>
            </div>
        </div>

        {/* --- Items Section --- */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <h2 className="text-xl font-semibold mb-4 text-gray-800">Bill Items (Optional)</h2>
            <div className="space-y-4">
                {items.map((item, itemIndex) => (
                    <div key={item.id} className="flex items-center space-x-3">
                        <input
                            type="text"
                            placeholder="Item Name"
                            value={item.name}
                            onChange={e => handleItemChange(itemIndex, 'name', e.target.value)}
                            className="flex-grow px-3 py-2 border border-gray-300 rounded-md placeholder-gray-700 text-gray-900"
                        />
                        <input
                            type="number"
                            placeholder="Price"
                            value={item.unit_price || ''}
                            onChange={e => handleItemChange(itemIndex, 'unit_price', e.target.value)}
                            min="0"
                            step="1"
                            className="w-32 px-3 py-2 border border-gray-300 rounded-md placeholder-gray-700 text-gray-900 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                        />
                        <input
                            type="number"
                            placeholder="Qty"
                            value={item.quantity || ''}
                            onChange={e => handleItemChange(itemIndex, 'quantity', e.target.value)}
                            min="1"
                            step="1"
                            className="w-24 px-3 py-2 border border-gray-300 rounded-md placeholder-gray-700 text-gray-900 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                        />
                        {items.length > 1 && (
                            <button
                                type="button"
                                onClick={() => handleRemoveItem(itemIndex)}
                                className="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-100 rounded-full focus:outline-none"
                                title="Remove Item"
                            >
                                <XMarkIcon className="h-5 w-5" />
                            </button>
                        )}
                    </div>
                ))}
                <button type="button" onClick={handleAddItem} className="text-sm font-medium text-indigo-600 hover:text-indigo-500 mt-2">
                    + Add Item
                </button>
                <div className="text-right text-sm mt-3 pt-2 border-t font-semibold text-gray-900">
                    Total From Items: {formatCurrency(itemizedTotalAmount, { rounding: false })}
                </div>
            </div>
        </div>

        {/* --- Split Method Section --- */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">Split Method</h2>
          <div className="flex justify-around bg-gray-100 p-1 rounded-lg">
            {(['equal', 'exact', 'item'] as SplitMethod[]).map(method => (
              <button key={method} type="button" onClick={() => setSplitMethod(method)} className={`px-4 py-2 text-sm font-medium rounded-md w-full ${splitMethod === method ? 'bg-white shadow text-gray-900' : 'text-gray-800'}`}>
                {method.charAt(0).toUpperCase() + method.slice(1)}
              </button>
            ))}
          </div>

          <div className="mt-4">
            {splitMethod === 'equal' && (
              <div>
                <div className="mb-2">
                    <label className="flex items-center">
                        <input type="checkbox" onChange={handleSelectAllParticipants} checked={splitParticipants.length === groupMembers.length} className="h-4 w-4 text-indigo-600 border-gray-300 rounded"/>
                        <span className="ml-2 text-sm font-medium text-gray-900">Select All</span>
                    </label>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {groupMembers.map(member => (
                    <label key={member.user.user_id} className="flex items-center p-2 border rounded-md">
                      <input type="checkbox" checked={splitParticipants.includes(member.user.user_id)} onChange={() => handleParticipantChange(member.user.user_id)} className="h-4 w-4 text-indigo-600 border-gray-300 rounded"/>
                      <span className="ml-2 text-sm truncate text-gray-900">{member.user.username || member.user.full_name}</span>
                    </label>
                  ))}
                </div>
                {splitParticipants.length > 0 && (
                    <p className="text-sm text-gray-900 mt-3 text-center">
                        {formatCurrency(totalAmountNumber, { rounding: false })} / {splitParticipants.length} participants = <span className="font-semibold">{formatCurrency(equalSplitAmount)} each</span>
                    </p>
                )}
              </div>
            )}
            {splitMethod === 'exact' && (
              <div className="space-y-3">
                {groupMembers.map(member => (
                  <div key={member.user.user_id} className="flex items-center space-x-3">
                    <span className="flex-1 text-sm text-gray-900">{member.user.username || member.user.full_name}</span>
                    <div className="flex-1">
                      <input type="number" value={exactSplits.find(s => s.user_id === member.user.user_id)?.amount_owed || ''} onChange={(e) => handleAmountChange(member.user.user_id, e.target.value)} min="0" step="1" className="block w-full px-3 py-2 border border-gray-300 rounded-md placeholder-gray-700 text-gray-900 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none" placeholder="0"/>
                    </div>
                  </div>
                ))}
                <div className="text-right text-sm mt-3 pt-2 border-t text-gray-900">
                  <span>Total: </span>
                  <span className={`font-semibold ${Math.abs(totalSplitAmount - totalAmountNumber) > 0.01 ? 'text-red-600' : 'text-green-600'}`}>{formatCurrency(totalSplitAmount, { rounding: false })}</span>
                  <span> / {formatCurrency(totalAmountNumber, { rounding: false })}</span>
                </div>
              </div>
            )}
            {splitMethod === 'item' && (
              <div className="space-y-4">
                  {items.map((item, itemIndex) => {
                      const assigned = getAssignedQuantityForItem(itemIndex);
                      const quantity = Number(item.quantity) || 0;
                      const isFullyAssigned = assigned === quantity;
                      
                      return (
                          <div key={item.id} className="border p-4 rounded-lg">
                              <h3 className="font-semibold text-gray-900">{item.name || `Item #${itemIndex + 1}`}</h3>
                              <h4 className={`text-sm font-medium mb-2 ${isFullyAssigned ? 'text-green-600' : 'text-red-600'}`}>
                                  Who took this? (Assigned: {assigned}/{quantity})
                              </h4>
                              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                {groupMembers.map(member => (
                                    <div key={member.user.user_id} className="flex items-center space-x-2">
                                        <label htmlFor={`item-${item.id}-member-${member.user.user_id}`} className="text-sm truncate flex-1 text-gray-900">{member.user.username || member.user.full_name}</label>
                                        <input type="number" id={`item-${item.id}-member-${member.user.user_id}`} value={item.assignments.find(a => a.user_id === member.user.user_id)?.quantity || ''} onChange={e => handleItemAssignmentChange(itemIndex, member.user.user_id, e.target.value)} min="0" max={quantity} step="1" className="w-16 px-2 py-1 border border-gray-300 rounded-md placeholder-gray-700 text-gray-900 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none" placeholder="0"/>
                                    </div>
                                ))}
                              </div>
                          </div>
                      );
                  })}
              </div>
            )}
          </div>
        </div>
        
        <div className="flex justify-end mt-8">
            <button type="button" onClick={() => router.back()} className="mr-3 py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-900 bg-white hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={isLoading || isFormInvalid} className="py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300">
                {isLoading ? 'Processing...' : 'Create Bill'}
            </button>
        </div>
        {error && <p className="text-red-500 text-sm mt-4 text-center">{error}</p>}

        <BillInfoModal
          isOpen={isConfirmationModalOpen}
          onClose={() => setIsConfirmationModalOpen(false)}
          onConfirm={handleConfirmSubmit}
          bill={getConfirmationBill()}
          isSubmitting={isLoading}
        />
    </form>
  );
};

export default CreateBillForm; 