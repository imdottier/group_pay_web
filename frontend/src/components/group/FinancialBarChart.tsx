import useSWR from 'swr';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import api from '@/lib/api';
import { formatCurrency } from '@/lib/utils';

interface UserFinancialBar {
  user_id: number;
  username: string;
  total_paid_out: number;
  total_owed_share: number;
  net_amount: number;
}
interface GroupFinancialBarSummary {
  group_id: number;
  bars: UserFinancialBar[];
}

interface FinancialBarChartProps {
  groupId: string;
}

const fetcher = (url: string) => api.get(url).then(res => res.data);

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const user = payload[0].payload;
    return (
      <div className="p-2 bg-white border border-gray-300 rounded shadow-lg">
        <div className="font-semibold text-gray-800 mb-1">{user.username}</div>
        <div className="text-green-600">Paid: {formatCurrency(user.total_paid_out)}</div>
        <div className="text-red-600">Owed: {formatCurrency(user.total_owed_share)}</div>
        <div className="text-gray-700 mt-1">Net: {formatCurrency(user.net_amount)}</div>
      </div>
    );
  }
  return null;
};

const FinancialBarChart = ({ groupId }: FinancialBarChartProps) => {
  const { data, error, isLoading } = useSWR<GroupFinancialBarSummary>(
    `/groups/${groupId}/financial_bar_summary`,
    fetcher
  );

  if (isLoading) return <div>Loading chart data...</div>;
  if (error) return <div className="text-red-500">Failed to load chart data. Please try again later.</div>;
  if (!data || data.bars.length === 0) {
    return <div className="text-center py-10 text-gray-500">No financial data available for this group.</div>;
  }

  return (
    <div style={{ width: '100%', height: 400 }}>
      <ResponsiveContainer>
        <BarChart
          data={data.bars}
          margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
          barSize={40}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis 
            dataKey="username" 
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
          <Bar dataKey="total_paid_out" fill="#22c55e" name="Paid" />
          <Bar dataKey="total_owed_share" fill="#ef4444" name="Owed" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default FinancialBarChart; 