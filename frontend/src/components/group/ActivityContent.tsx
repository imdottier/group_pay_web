'use client';

import { useEffect, useState, useMemo } from 'react';
import api from '@/lib/api';
import { ChevronLeftIcon, ChevronRightIcon, FunnelIcon } from '@heroicons/react/24/outline';

// From backend/models.py
type AuditActionType = 
  | "bill_created" | "bill_updated" | "bill_deleted"
  | "payment_created" | "payment_updated" | "payment_deleted"
  | "member_invited" | "member_added" | "member_left" | "member_removed" | "member_role_updated"
  | "group_created" | "group_details_updated";

// For frontend display and filtering
export type ActivityCategory = "All" | "Bills" | "Payments" | "Members" | "Group";

interface User {
  user_id: number;
  username: string;
}

interface AuditLogEntry {
  id: number;
  timestamp: string; // DateTime string
  action_type: AuditActionType;
  actor_user: User | null;
  display_message: string;
  // other related_ids might be useful later
}

interface GroupActivityFeedResponse {
  group_id: number;
  activities: AuditLogEntry[];
  // Assuming API might provide total count for pagination in the future
  total_activities?: number; 
  has_next_page?: boolean;
  has_prev_page?: boolean;
}

interface ActivityContentProps {
  groupId: string;
}

const ITEMS_PER_PAGE = 20;

// --- In-memory cache for activities ---
const activityCache = new Map<string, GroupActivityFeedResponse>();

const formatDate = (dateString?: string | null) => {
  if (!dateString) return 'N/A';
  try {
    return new Date(dateString).toLocaleString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric', 
      hour: '2-digit', minute: '2-digit'
    });
  } catch (e) {
    return dateString;
  }
};

// Helper to map detailed AuditActionType to broader categories for filtering/display
const getCategoryForActionType = (actionType: AuditActionType): ActivityCategory => {
  if (actionType.startsWith('bill_')) return "Bills";
  if (actionType.startsWith('payment_')) return "Payments";
  if (actionType.startsWith('member_')) return "Members";
  if (actionType.startsWith('group_')) return "Group";
  return "All"; // Fallback, though ideally all types are mapped
};

const ActivityContent: React.FC<ActivityContentProps> = ({ groupId }) => {
  const [activities, setActivities] = useState<AuditLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(0); // 0-indexed
  const [selectedCategory, setSelectedCategory] = useState<ActivityCategory>("All");
  const [hasNextPage, setHasNextPage] = useState(false);

  useEffect(() => {
    const fetchActivities = async () => {
      const cacheKey = `${groupId}-${currentPage}`;
      if (activityCache.has(cacheKey) && selectedCategory === 'All') {
        const cachedData = activityCache.get(cacheKey)!;
        setActivities(cachedData.activities);
        setHasNextPage(cachedData.has_next_page ?? (cachedData.activities.length === ITEMS_PER_PAGE));
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      try {
        const params: any = {
          skip: currentPage * ITEMS_PER_PAGE,
          limit: ITEMS_PER_PAGE,
        };
        
        const response = await api.get<GroupActivityFeedResponse>(`/groups/${groupId}/activities`, { params });
        setActivities(response.data.activities);
        const newHasNextPage = response.data.has_next_page ?? (response.data.activities.length === ITEMS_PER_PAGE);
        setHasNextPage(newHasNextPage);
        
        // Only cache if we are not filtering, as the API returns all categories
        if(selectedCategory === 'All') {
            activityCache.set(cacheKey, { ...response.data, has_next_page: newHasNextPage });
        }
        
        setError(null);
      } catch (err) {
        console.error("Failed to fetch activities:", err);
        setError("Could not load group activities. Please try again.");
      }
      setIsLoading(false);
    };
    
    if (groupId) {
      fetchActivities();
    }
  }, [groupId, currentPage, selectedCategory]);

  const filteredActivities = useMemo(() => {
    if (selectedCategory === "All") {
      return activities;
    }
    return activities.filter(act => getCategoryForActionType(act.action_type) === selectedCategory);
  }, [activities, selectedCategory]);

  const handleNextPage = () => {
    if(hasNextPage) {
        setCurrentPage(prev => prev + 1);
    }
  };

  const handlePreviousPage = () => {
    setCurrentPage(prev => Math.max(0, prev - 1));
  };

  if (isLoading) {
    return <div className="text-center py-10">Loading activities...</div>;
  }

  if (error) {
    return <div className="bg-white shadow-sm p-6 rounded-lg text-red-500">{error}</div>;
  }

  const categories: ActivityCategory[] = ["All", "Bills", "Payments", "Members", "Group"];

  return (
    <div className="bg-white shadow-sm p-6 rounded-lg">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold text-gray-700">Group Activity</h2>
        {/* Filter Dropdown Placeholder */}
        <div className="relative">
          <select 
            value={selectedCategory}
            onChange={(e) => {
              setSelectedCategory(e.target.value as ActivityCategory);
              setCurrentPage(0);
              activityCache.clear(); // Clear cache when category changes
            }}
            className="appearance-none block w-full bg-gray-50 border border-gray-300 text-gray-700 py-2 px-3 pr-8 rounded-md leading-tight focus:outline-none focus:bg-white focus:border-gray-500 text-sm"
          >
            {categories.map(cat => <option key={cat} value={cat}>{cat} Activity</option>)}
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-700">
            <FunnelIcon className="h-4 w-4"/>
          </div>
        </div>
      </div>

      {filteredActivities.length === 0 ? (
        <p className="text-gray-500 text-center py-5">No activities found for this category.</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-1/4">Timestamp</th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-1/5">Category</th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-auto">Message</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredActivities.map((activity) => (
                  <tr key={activity.id}>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-600">{formatDate(activity.timestamp)}</td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700 font-medium">{getCategoryForActionType(activity.action_type)}</td>
                    <td className="px-4 py-4 text-sm text-gray-800">
                      {activity.display_message}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Basic Pagination (improvement: disable buttons when no more pages) */}
          <div className="mt-6 flex justify-between items-center">
            <button
              onClick={handlePreviousPage}
              disabled={currentPage === 0}
              className="flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeftIcon className="h-5 w-5 mr-2" />
              Previous
            </button>
            <span className="text-sm text-gray-700">
              Page {currentPage + 1}
            </span>
            <button
              onClick={handleNextPage}
              disabled={!hasNextPage}
              className="flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRightIcon className="h-5 w-5 ml-2" />
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default ActivityContent; 