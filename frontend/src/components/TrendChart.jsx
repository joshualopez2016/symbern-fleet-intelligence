import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'

// A single time-series line with optional threshold reference lines.
// `refLines` = [{ y, color, label }]. Colors/axes match the dark theme.
export default function TrendChart({ title, data, dataKey, unit, color, refLines = [], domain }) {
  return (
    <div className="chart">
      <div className="chart-title">{title}</div>
      <ResponsiveContainer width="100%" height={190}>
        <LineChart data={data} margin={{ top: 8, right: 14, bottom: 0, left: -8 }}>
          <CartesianGrid stroke="#2a3039" strokeDasharray="3 3" />
          <XAxis
            dataKey="time"
            tick={{ fill: '#8b95a5', fontSize: 11 }}
            minTickGap={44}
            tickLine={false}
          />
          <YAxis
            domain={domain || ['auto', 'auto']}
            tick={{ fill: '#8b95a5', fontSize: 11 }}
            width={46}
            unit={unit}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: '#1e232c',
              border: '1px solid #2a3039',
              borderRadius: 8,
              color: '#e6e9ef',
              fontSize: 12,
            }}
            labelStyle={{ color: '#8b95a5' }}
            formatter={(v) => [`${Number(v).toFixed(1)}${unit || ''}`, dataKey]}
          />
          {refLines.map((r, i) => (
            <ReferenceLine
              key={i}
              y={r.y}
              stroke={r.color}
              strokeDasharray="5 4"
              ifOverflow="extendDomain"
              label={{ value: r.label, position: 'right', fill: r.color, fontSize: 10 }}
            />
          ))}
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            dot={false}
            isAnimationActive={false}
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
