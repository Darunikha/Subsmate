import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatMonth, formatMonthYear, money, moneyCompact } from '../lib/format';

// Validated categorical order (CVD-safe on the light surface).
export const SERIES = ['#6d5ce8', '#0e9f8f', '#c8731f'];
const AXIS = { fontSize: 12, fill: '#8a8a99' };
const GRID = '#eeeef3';

function ChartTooltip({ active, payload, label, formatter = (v) => v, labelFormatter = formatMonthYear }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <p>{labelFormatter(label)}</p>
      {payload.map((entry) => (
        <div key={entry.dataKey} className="chart-tooltip-row">
          <span className="legend-swatch" style={{ background: entry.color }} />
          <span>{entry.name}</span>
          <strong>{formatter(entry.value)}</strong>
        </div>
      ))}
    </div>
  );
}

export function RevenueArea({ data, height = 240 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={SERIES[0]} stopOpacity={0.18} />
            <stop offset="100%" stopColor={SERIES[0]} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="month" tickFormatter={formatMonth} tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={moneyCompact} tick={AXIS} axisLine={false} tickLine={false} width={56} />
        <Tooltip content={<ChartTooltip formatter={money} />} cursor={{ stroke: '#c9c3f5' }} />
        <Area isAnimationActive={false}
          type="monotone"
          dataKey="revenue"
          name="Revenue"
          stroke={SERIES[0]}
          strokeWidth={2}
          fill="url(#revenueFill)"
          dot={false}
          activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function RevenueBars({ data, height = 260 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 10, right: 8, left: 0, bottom: 0 }} barCategoryGap="28%">
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="month" tickFormatter={formatMonth} tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={moneyCompact} tick={AXIS} axisLine={false} tickLine={false} width={56} />
        <Tooltip content={<ChartTooltip formatter={money} />} cursor={{ fill: 'rgba(109,92,232,0.06)' }} />
        <Bar isAnimationActive={false} dataKey="revenue" name="Revenue" fill={SERIES[0]} radius={[4, 4, 0, 0]} maxBarSize={36} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function TrendLines({ data, height = 260 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="month" tickFormatter={formatMonth} tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} width={32} />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#d9d9e3' }} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
        <Line isAnimationActive={false} type="linear" dataKey="new_subscriptions" name="New" stroke={SERIES[0]} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
        <Line isAnimationActive={false} type="linear" dataKey="renewals" name="Renewals" stroke={SERIES[1]} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
        <Line isAnimationActive={false} type="linear" dataKey="cancellations" name="Cancellations" stroke={SERIES[2]} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function HorizontalBars({ data, dataKey, labelKey, name, height, formatter = (v) => v }) {
  return (
    <ResponsiveContainer width="100%" height={height || Math.max(data.length * 44, 120)}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, left: 0, bottom: 0 }} barCategoryGap="30%">
        <CartesianGrid stroke={GRID} horizontal={false} />
        <XAxis type="number" allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} tickFormatter={formatter} />
        <YAxis type="category" dataKey={labelKey} tick={{ ...AXIS, fill: '#4b4b5a' }} axisLine={false} tickLine={false} width={150} />
        <Tooltip
          content={<ChartTooltip formatter={formatter} labelFormatter={(l) => l} />}
          cursor={{ fill: 'rgba(109,92,232,0.06)' }}
        />
        <Bar isAnimationActive={false} dataKey={dataKey} name={name} fill={SERIES[0]} radius={[0, 4, 4, 0]} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}
