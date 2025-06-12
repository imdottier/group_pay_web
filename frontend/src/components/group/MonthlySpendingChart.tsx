'use client';

import useSWR from 'swr';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import api from '@/lib/api';
import { formatCurrency } from '@/lib/utils';

interface MonthlySpendingChartProps {
  groupId: string;
  year: number;
}

interface MonthlySpendingData {
  [month: number]: number;
}

const fetcher = async (url: string): Promise<MonthlySpendingData> => {
  const res = await api.get(url);
  return res.data as MonthlySpendingData;
};

const months = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
];

const MonthlySpendingChart = ({ groupId, year }: MonthlySpendingChartProps) => {
  const { data, error, isLoading } = useSWR<MonthlySpendingData>(
    `/statistics/groups/${groupId}/monthly-spending?year=${year}`,
    fetcher
  );

  if (isLoading) return <div>Loading yearly spending data...</div>;
  if (error) return <div className="text-red-500">Failed to load yearly spending data. Please try again later.</div>;
  if (!data) return <div className="text-center py-10 text-gray-500">No yearly spending data available.</div>;

  // Transform data for recharts
  const chartData = months.map((name, idx) => ({
    month: name,
    total: data[idx + 1] || 0,
  }));

  return (
    <div style={{ width: '100%', height: 320 }}>
      <ResponsiveContainer>
        <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }} barSize={32}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="month" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={(value) => formatCurrency(value)} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value: number) => formatCurrency(value)} />
          <Bar dataKey="total" fill="#6366f1" name="Total Spending" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default MonthlySpendingChart; 