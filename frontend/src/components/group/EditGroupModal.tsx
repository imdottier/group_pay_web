import React, { useState, useEffect } from 'react';
import api from '@/lib/api';
import { XMarkIcon } from '@heroicons/react/24/outline';

// Interface for the group data modal expects and sends back
// This should align with GroupDetails in page.tsx and backend response
interface GroupData {
  group_id: number;
  group_name: string;
  description: string | null;
  // If your Group model has more fields and they are returned by PUT /groups/{group_id},
  // include them here to ensure the onGroupUpdated callback has the full updated object.
  // For example, if members are returned: members?: any[]; 
}

interface GroupUpdatePayload {
  group_name?: string;
  description?: string | null;
}

interface EditGroupModalProps {
  isOpen: boolean;
  onClose: () => void;
  group: GroupData | null; // Current group data to pre-fill
  onGroupUpdated: (updatedGroupData: GroupData) => void;
}

const EditGroupModal: React.FC<EditGroupModalProps> = ({
  isOpen,
  onClose,
  group,
  onGroupUpdated,
}) => {
  const [groupName, setGroupName] = useState('');
  const [description, setDescription] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (group && isOpen) { // Populate form when modal opens with group data
      setGroupName(group.group_name);
      setDescription(group.description || '');
      setError(null); // Clear previous errors
    } else if (!isOpen) {
      // Optionally reset form when modal is closed if desired, though useEffect handles re-population
      // setGroupName('');
      // setDescription('');
      // setError(null);
    }
  }, [group, isOpen]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!group) {
      setError("Group data is not available to edit.");
      return;
    }

    setIsLoading(true);
    setError(null);

    const payload: GroupUpdatePayload = {};
    let hasChanges = false;

    // Only include fields in payload if they have changed
    if (groupName.trim() !== group.group_name) {
      payload.group_name = groupName.trim();
      hasChanges = true;
    }
    // Normalize null/empty string for description comparison and payload
    const currentDesc = group.description || '';
    const newDesc = description.trim();
    if (newDesc !== currentDesc) {
      payload.description = newDesc === '' ? null : newDesc; // Send null if empty, otherwise trimmed value
      hasChanges = true;
    }

    if (!hasChanges) {
      // setError("No changes were made."); // Optional: inform user no changes were made
      setIsLoading(false);
      onClose(); // Close modal if no changes
      return;
    }
    
    try {
      // Backend expects PUT /groups/{group_id}
      const response = await api.put<GroupData>(`/groups/${group.group_id}`, payload);
      onGroupUpdated(response.data); // Pass the full updated group data back
      onClose(); // Close modal on success
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to update group details.';
      setError(errorMsg);
      console.error("Failed to update group:", err);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) { // Only render if isOpen is true
    return null;
  }

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(0,0,0,0.5)] backdrop-blur-sm transition-opacity duration-300 ease-in-out"
      onClick={(e) => {
        if (e.target === e.currentTarget) { 
          onClose();
        }
      }}
    >
      <div 
        className="bg-white p-6 rounded-lg shadow-xl w-full max-w-md m-4 transform transition-all duration-300 ease-in-out scale-100 opacity-100" 
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-5">
          <h2 className="text-xl font-semibold text-gray-800">Edit Group Details</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-full hover:bg-gray-100"
            aria-label="Close modal"
          >
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label htmlFor="editGroupName" className="block text-sm font-medium text-gray-900 mb-1">
              Group Name
            </label>
            <input
              type="text"
              id="editGroupName"
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900"
              required
              maxLength={100}
            />
          </div>

          <div className="mb-6">
            <label htmlFor="editDescription" className="block text-sm font-medium text-gray-900 mb-1">
              Description <span className="text-xs text-gray-600">(Optional)</span>
            </label>
            <textarea
              id="editDescription"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900"
              maxLength={255}
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
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
            >
              {isLoading ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default EditGroupModal; 