'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { User } from '@/types';
import { formatCurrency } from '@/lib/utils';

interface GroupMember {
    user: {
        user_id: number;
        username: string;
    };
}

interface CreatePaymentFormProps {
    groupId: string;
}

interface PaymentDetails {
    payeeId: number;
    amount: string;
    notes: string;
}

const CreatePaymentForm = ({ groupId }: CreatePaymentFormProps) => {
    const router = useRouter();
    const [groupMembers, setGroupMembers] = useState<GroupMember[]>([]);
    const [currentUser, setCurrentUser] = useState<{user_id: number} | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isConfirming, setIsConfirming] = useState(false);
    
    const [paymentDetails, setPaymentDetails] = useState<PaymentDetails>({
        payeeId: 0,
        amount: '',
        notes: ''
    });

    useEffect(() => {
        const fetchInitialData = async () => {
            setIsLoading(true);
            try {
                const [membersRes, userRes] = await Promise.all([
                    api.get<GroupMember[]>(`/groups/${groupId}/members`),
                    api.get<{user_id: number}>('/users/me')
                ]);
                
                setGroupMembers(membersRes.data);
                setCurrentUser(userRes.data);
                
                // Set default payee to the first member who is not the current user
                const firstOtherMember = membersRes.data.find(m => m.user.user_id !== userRes.data.user_id);
                if (firstOtherMember) {
                    setPaymentDetails(prev => ({ ...prev, payeeId: firstOtherMember.user.user_id }));
                } else if (membersRes.data.length > 0) {
                    setPaymentDetails(prev => ({ ...prev, payeeId: membersRes.data[0].user.user_id }));
                }

            } catch (err) {
                setError('Failed to load group members. Please try again.');
                console.error(err);
            }
            setIsLoading(false);
        };
        fetchInitialData();
    }, [groupId]);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
        const { name, value } = e.target;
        setPaymentDetails(prev => ({ ...prev, [name]: value }));
    };

    const handleReview = (e: React.FormEvent) => {
        e.preventDefault();
        if (validatePayment()) {
            setIsConfirming(true);
        }
    };
    
    const validatePayment = () => {
        setError(null);
        if (!paymentDetails.payeeId || paymentDetails.payeeId === 0) {
            setError('Please select a payee.');
            return false;
        }
        const amountNumber = parseFloat(paymentDetails.amount);
        if (isNaN(amountNumber) || amountNumber <= 0) {
            setError('Please enter a valid amount.');
            return false;
        }
        return true;
    };

    const handleSubmit = async () => {
        if (!validatePayment()) return;

        setIsLoading(true);
        setError(null);

        try {
            await api.post(`/groups/${groupId}/payments`, {
                payee_id: Number(paymentDetails.payeeId),
                amount: parseFloat(paymentDetails.amount),
                notes: paymentDetails.notes || null
            });
            
            // Clear cache for this group's payments to force refresh
            // Note: This simple approach assumes a global cache object or context.
            // A more robust solution might involve a shared cache instance.
            // For now, we rely on the user navigating back and the cache being stale.
            
            router.push(`/groups/${groupId}`);

        } catch (err: any) {
            setError(err.response?.data?.detail || 'An unexpected error occurred.');
            console.error(err);
        } finally {
            setIsLoading(false);
            setIsConfirming(false);
        }
    };
    
    const payee = groupMembers.find(m => m.user.user_id === Number(paymentDetails.payeeId))?.user;

    if (isLoading && !groupMembers.length) {
        return <div className="text-center">Loading form...</div>;
    }

    return (
        <>
            <h2 className="text-2xl font-bold mb-6 text-gray-900">Record a Payment</h2>
            <form onSubmit={handleReview}>
                <div className="mb-4">
                    <label htmlFor="payeeId" className="block text-sm font-medium text-gray-900 mb-1">Who did you pay?</label>
                    <select
                        id="payeeId"
                        name="payeeId"
                        value={paymentDetails.payeeId}
                        onChange={handleInputChange}
                        className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-gray-900"
                        required
                    >
                        <option value={0} disabled>Select a member</option>
                        {groupMembers
                            .filter(m => m.user.user_id !== currentUser?.user_id)
                            .map(member => (
                                <option key={member.user.user_id} value={member.user.user_id}>
                                    {member.user.username}
                                </option>
                        ))}
                    </select>
                </div>
                
                <div className="mb-4">
                    <label htmlFor="amount" className="block text-sm font-medium text-gray-900 mb-1">Amount</label>
                    <div className="relative">
                        <input
                            type="number"
                            id="amount"
                            name="amount"
                            value={paymentDetails.amount}
                            onChange={handleInputChange}
                            placeholder="0"
                            className="block w-full px-3 py-2 pl-3 pr-12 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-gray-900"
                            step="1000"
                            required
                        />
                        <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                            <span className="text-gray-500 sm:text-sm">VND</span>
                        </div>
                    </div>
                </div>

                <div className="mb-6">
                    <label htmlFor="notes" className="block text-sm font-medium text-gray-900 mb-1">Notes (Optional)</label>
                    <textarea
                        id="notes"
                        name="notes"
                        value={paymentDetails.notes}
                        onChange={handleInputChange}
                        rows={3}
                        className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-gray-900"
                    />
                </div>
                
                {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

                <div className="flex justify-end">
                    <button type="submit" disabled={isLoading} className="bg-indigo-600 text-white font-bold py-2 px-4 rounded-md hover:bg-indigo-700 disabled:bg-indigo-400">
                        {isLoading ? 'Processing...' : 'Submit Payment'}
                    </button>
                </div>
            </form>

            {isConfirming && (
                <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center">
                    <div className="bg-white p-8 rounded-lg shadow-2xl max-w-sm w-full">
                        <h3 className="text-xl font-bold mb-4 text-gray-900">Confirm Payment</h3>
                        <div className="space-y-3 text-gray-800">
                            <p>You are about to record a payment of <strong className="text-indigo-600 font-semibold">{formatCurrency(parseFloat(paymentDetails.amount), { rounding: false })}</strong> to <strong className="text-indigo-600 font-semibold">{payee?.username}</strong>.</p>
                            {paymentDetails.notes && (
                                <p>Notes: <span className="italic">"{paymentDetails.notes}"</span></p>
                            )}
                        </div>
                        <div className="mt-6 flex justify-end space-x-4">
                            <button onClick={() => setIsConfirming(false)} className="text-gray-700 font-semibold py-2 px-4 rounded-md hover:bg-gray-200 transition-colors">
                                Cancel
                            </button>
                            <button onClick={handleSubmit} disabled={isLoading} className="bg-green-600 text-white font-bold py-2 px-4 rounded-md hover:bg-green-700 disabled:bg-green-400">
                                {isLoading ? 'Submitting...' : 'Yes, Submit'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

export default CreatePaymentForm; 