'use client';

import useSWR from 'swr';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import api from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import { useState } from 'react';

interface SpendingData {
  category_name: string;
  total_amount: number;
}

const fetcher = (url: string) => api.get(url).then(res => res.data);

interface SpendingByCategoryChartProps {
  groupId: string;
  year: number;
  month: number;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="p-2 bg-white border border-gray-300 rounded shadow-lg">
        <p className="font-semibold">{`${label}`}</p>
        <p className="text-indigo-600">{`Amount: ${formatCurrency(payload[0].value)}`}</p>
      </div>
    );
  }

  return null;
};

const SpendingByCategoryChart = ({ groupId, year, month }: SpendingByCategoryChartProps) => {
  const [includeUncategorized, setIncludeUncategorized] = useState(true);
  const { data, error, isLoading, mutate } = useSWR<SpendingData[]>(
    `/statistics/groups/${groupId}/spending-by-category?year=${year}&month=${month}&include_uncategorized=${includeUncategorized}`,
    fetcher
  );

  const handleToggle = () => {
    setIncludeUncategorized((prev) => !prev);
    // SWR will refetch automatically due to key change
  };

  if (isLoading) return <div>Loading chart data...</div>;
  if (error) return <div className="text-red-500">Failed to load chart data. Please try again later.</div>;
  if (!data || data.length === 0) {
    return <div className="text-center py-10 text-gray-500">No spending data available for this period.</div>;
  }

  return (
    <div style={{ width: '100%', height: 400 }}>
      <div className="flex items-center mb-2">
        <label className="flex items-center space-x-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={includeUncategorized}
            onChange={handleToggle}
            className="form-checkbox h-4 w-4 text-indigo-600 transition duration-150 ease-in-out"
          />
          <span>Include Uncategorized</span>
        </label>
      </div>
      <ResponsiveContainer>
        <BarChart
          data={data}
          margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
          barSize={40}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis 
            dataKey="category_name" 
            angle={-45}
            textAnchor="end"
            height={70}
            interval={0}
            tick={{ fontSize: 12 }}
          />
          <YAxis
            tickFormatter={(value) => formatCurrency(value, { notation: 'compact' })}
            tick={{ fontSize: 12 }}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(233, 236, 239, 0.5)' }}/>
          <Legend />
          <Bar dataKey="total_amount" fill="#4f46e5" name="Spending by Category" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default SpendingByCategoryChart; 