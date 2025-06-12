import React, { useState, useEffect, useMemo } from 'react';
import api from '@/lib/api';
import { XMarkIcon, CheckIcon, ChevronUpDownIcon } from '@heroicons/react/24/outline';
import { Combobox } from '@headlessui/react';

function classNames(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}

// This interface should match the one in TransactionsContent.tsx
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

// Matches the backend's TransactionCategory schema
interface Category {
  category_id: number;
  name: string;
}

const NEW_CATEGORY_ID = -1; // Sentinel ID for a new category

interface AddTransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTransactionAdded: (newTransaction: Transaction) => void;
}

const AddTransactionModal: React.FC<AddTransactionModalProps> = ({
  isOpen,
  onClose,
  onTransactionAdded,
}) => {
  const [amount, setAmount] = useState<number | ''>('');
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(null);
  const [query, setQuery] = useState('');
  const [categories, setCategories] = useState<Category[]>([]);
  const [note, setNote] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    if (isOpen) {
      // Reset form when modal opens
      setAmount('');
      setSelectedCategory(null);
      setQuery('');
      setNote('');
      setDate(new Date().toISOString().split('T')[0]);
      setError(null);

      // Fetch categories when modal opens
      const fetchCategories = async () => {
        try {
          const response = await api.get<Category[]>('/categories/');
          setCategories(response.data);
        } catch (err) {
          console.error("Failed to fetch categories:", err);
          setError("Could not load categories.");
        }
      };
      fetchCategories();
    }
  }, [isOpen]);

  const filteredCategories = useMemo(() => {
    const lowerCaseQuery = query.toLowerCase();
    if (lowerCaseQuery === '') {
      return categories;
    }
    
    const filtered = categories.filter((category) =>
      category.name.toLowerCase().includes(lowerCaseQuery)
    );

    const isQueryAnExistingCategory = categories.some(c => c.name.toLowerCase() === lowerCaseQuery);
    if (!isQueryAnExistingCategory) {
      filtered.push({ category_id: NEW_CATEGORY_ID, name: `Create "${query}"` });
    }
    
    return filtered;
  }, [query, categories]);


  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (amount === '' || amount <= 0) {
      setError("Please enter a valid amount.");
      return;
    }
    if (!selectedCategory && query.trim() === '') {
      setError("Please select or enter a category.");
      return;
    }

    setIsLoading(true);
    setError(null);

    let categoryInput;
    const isNew = selectedCategory?.category_id === NEW_CATEGORY_ID;
    const newCategoryName = query.trim();

    if (isNew && newCategoryName) {
        categoryInput = { type: 'new', name: newCategoryName };
    } else if (selectedCategory) {
        categoryInput = { type: 'existing', category_id: selectedCategory.category_id };
    } else {
        // Fallback for when user types a category name and doesn't select from the list
        const existing = categories.find(c => c.name.toLowerCase() === newCategoryName.toLowerCase());
        categoryInput = existing 
            ? { type: 'existing', category_id: existing.category_id }
            : { type: 'new', name: newCategoryName };
    }
    
    const payload = {
      amount,
      transaction_date: new Date(date).toISOString(),
      notes: note.trim() || null,
      category_input: categoryInput,
    };

    try {
      const response = await api.post<Transaction>('/transactions/', payload);
      onTransactionAdded(response.data);
      onClose();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to add transaction.';
      setError(errorMsg);
      console.error("Failed to add transaction:", err);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(0,0,0,0.5)] backdrop-blur-sm"
      onClick={onClose}
    >
      <div 
        className="bg-white p-6 rounded-lg shadow-xl w-full max-w-md m-4" 
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-5">
          <h2 className="text-xl font-semibold text-gray-800">Add New Transaction</h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-100">
            <XMarkIcon className="h-6 w-6 text-gray-400" />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label htmlFor="amount" className="block text-sm font-medium text-gray-900 mb-1">Amount</label>
            <input
              type="number"
              id="amount"
              value={amount}
              onChange={(e) => setAmount(e.target.value === '' ? '' : parseFloat(e.target.value))}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-gray-900 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              required
              placeholder="10000"
              step="1000"
            />
          </div>

          <div className="mb-4">
            <label htmlFor="category" className="block text-sm font-medium text-gray-900 mb-1">Category</label>
            <Combobox value={selectedCategory} onChange={setSelectedCategory} nullable>
              <div className="relative mt-1">
                <Combobox.Input
                  className="w-full rounded-md border border-gray-300 bg-white py-2 pl-3 pr-10 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm text-gray-900"
                  onChange={(event) => setQuery(event.target.value)}
                  displayValue={(category: Category | null) => category?.name.startsWith('Create "') ? query : category?.name ?? query}
                  placeholder="Select or create category"
                />
                <Combobox.Button className="absolute inset-y-0 right-0 flex items-center rounded-r-md px-2 focus:outline-none">
                  <ChevronUpDownIcon className="h-5 w-5 text-gray-400" aria-hidden="true" />
                </Combobox.Button>

                {filteredCategories.length > 0 && (
                  <Combobox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm">
                    {filteredCategories.map((category) => (
                      <Combobox.Option
                        key={category.category_id}
                        value={category}
                        className={({ active }) =>
                          classNames(
                            'relative cursor-default select-none py-2 pl-3 pr-9',
                            active ? 'bg-indigo-600 text-white' : 'text-gray-900'
                          )
                        }
                      >
                        {({ active, selected }: { active: boolean; selected: boolean }) => (
                          <>
                            <span className={classNames('block truncate', selected ? 'font-semibold' : '')}>
                              {category.name}
                            </span>
                            {selected && (
                              <span
                                className={classNames(
                                  'absolute inset-y-0 right-0 flex items-center pr-4',
                                  active ? 'text-white' : 'text-indigo-600'
                                )}
                              >
                                <CheckIcon className="h-5 w-5" aria-hidden="true" />
                              </span>
                            )}
                          </>
                        )}
                      </Combobox.Option>
                    ))}
                  </Combobox.Options>
                )}
              </div>
            </Combobox>
          </div>

          <div className="mb-4">
            <label htmlFor="date" className="block text-sm font-medium text-gray-900 mb-1">Date</label>
            <input
              type="date"
              id="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-gray-900"
              required
            />
          </div>

          <div className="mb-6">
            <label htmlFor="note" className="block text-sm font-medium text-gray-900 mb-1">
              Note <span className="text-xs text-gray-600">(Optional)</span>
            </label>
            <textarea
              id="note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-gray-900"
              placeholder="Add any details here"
            />
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 text-red-700 border border-red-200 rounded-md text-sm">
              {error}
            </div>
          )}

          <div className="flex justify-end space-x-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
            >
              {isLoading ? 'Adding...' : 'Add Transaction'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddTransactionModal; 