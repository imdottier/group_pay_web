import { useEffect, useState, Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import api from '@/lib/api';

interface Inviter {
    user_id: number;
    username: string;
}

interface Group {
    group_id: number;
    group_name: string;
}

interface GroupInvitation {
    invitation_id: number;
    group: Group;
    inviter: Inviter;
    status: string;
}

interface GroupInvitationsModalProps {
    isOpen: boolean;
    onClose: () => void;
    onInvitationAccepted: () => void;
}

const GroupInvitationsModal = ({ isOpen, onClose, onInvitationAccepted }: GroupInvitationsModalProps) => {
    const [invitations, setInvitations] = useState<GroupInvitation[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState<number | null>(null);
    const [error, setError] = useState<string | null>(null);

    const fetchInvitations = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await api.get<GroupInvitation[]>('/invitations/pending');
            setInvitations(response.data);
        } catch (err) {
            setError('Could not load your pending group invitations.');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchInvitations();
        }
    }, [isOpen]);

    const handleResponse = async (invitation_id: number, status: 'accepted' | 'declined') => {
        setIsSubmitting(invitation_id);
        try {
            await api.put(`/invitations/${invitation_id}`, { status });
            if (status === 'accepted') {
                onInvitationAccepted();
            }
            // Refresh list after action
            fetchInvitations();
        } catch (err) {
            setError(`Failed to ${status} the invitation.`);
        } finally {
            setIsSubmitting(null);
        }
    };

    return (
        <Transition appear show={isOpen} as={Fragment}>
            <Dialog as="div" className="relative z-10" onClose={onClose}>
                <Transition.Child
                    as={Fragment}
                    enter="ease-out duration-300"
                    enterFrom="opacity-0"
                    enterTo="opacity-100"
                    leave="ease-in duration-200"
                    leaveFrom="opacity-100"
                    leaveTo="opacity-0"
                >
                    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm" />
                </Transition.Child>

                <div className="fixed inset-0 overflow-y-auto">
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
                            <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
                                <Dialog.Title as="h3" className="text-lg font-medium leading-6 text-gray-900">
                                    Group Invitations
                                </Dialog.Title>
                                <div className="mt-4">
                                    {isLoading ? (
                                        <div className="flex justify-center items-center h-24">
                                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
                                        </div>
                                    ) : error ? (
                                        <p className="text-sm text-red-500">{error}</p>
                                    ) : invitations.length === 0 ? (
                                        <p className="text-sm text-gray-500">You have no pending invitations.</p>
                                    ) : (
                                        <ul className="space-y-4 max-h-60 overflow-y-auto">
                                            {invitations
                                                .filter(inv => inv.group && inv.inviter)
                                                .map((inv) => (
                                                <li key={inv.invitation_id} className="p-4 border border-gray-200 rounded-lg">
                                                    <p className="text-sm text-gray-700">
                                                        <span className="font-semibold">{inv.inviter.username}</span> has invited you to join <span className="font-semibold">{inv.group.group_name}</span>.
                                                    </p>
                                                    <div className="mt-3 flex justify-end space-x-3">
                                                        <button
                                                            onClick={() => handleResponse(inv.invitation_id, 'accepted')}
                                                            disabled={isSubmitting !== null}
                                                            className="inline-flex justify-center rounded-md border border-transparent bg-green-500 px-4 py-1.5 text-sm font-medium text-white hover:bg-green-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-green-500 focus-visible:ring-offset-2 disabled:opacity-50"
                                                        >
                                                            {isSubmitting === inv.invitation_id ? 'Accepting...' : 'Accept'}
                                                        </button>
                                                        <button
                                                            onClick={() => handleResponse(inv.invitation_id, 'declined')}
                                                            disabled={isSubmitting !== null}
                                                            className="inline-flex justify-center rounded-md border border-transparent bg-red-500 px-4 py-1.5 text-sm font-medium text-white hover:bg-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 disabled:opacity-50"
                                                        >
                                                            {isSubmitting === inv.invitation_id ? 'Declining...' : 'Decline'}
                                                        </button>
                                                    </div>
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                </div>

                                <div className="mt-6">
                                    <button
                                        type="button"
                                        className="inline-flex justify-center rounded-md border border-transparent bg-gray-100 px-4 py-2 text-sm font-medium text-gray-900 hover:bg-gray-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-500 focus-visible:ring-offset-2"
                                        onClick={onClose}
                                    >
                                        Close
                                    </button>
                                </div>
                            </Dialog.Panel>
                        </Transition.Child>
                    </div>
                </div>
            </Dialog>
        </Transition>
    );
};

export default GroupInvitationsModal; 