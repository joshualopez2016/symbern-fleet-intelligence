import { useState } from 'react'
import { fetchAlarms } from '../api'
import { usePolling } from '../usePolling'

// Human-readable labels + the unit for each alarm's tripping value.
const ALARM_META = {
  LOW_SOC: { label: 'Low state of charge', unit: '%' },
  LOW_VOLTAGE: { label: 'Low pack voltage', unit: ' V' },
  OVER_TEMP: { label: 'Over temperature', unit: ' °C' },
}

function timeAgo(ts) {
  const s = Math.max(0, Math.floor((Date.now() - new Date(ts).getTime()) / 1000))
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

// Live feed of currently-open alarms (cleared ones drop off automatically as the
// simulator clears them). Newest first, severity-colored, click a row to open
// that device's drill-down.
export default function AlertsPanel({ onSelect }) {
  const { data } = usePolling(() => fetchAlarms({ active: true, limit: 100 }), 3000, [])
  const [open, setOpen] = useState(true)
  const alarms = data?.alarms ?? []

  if (data && alarms.length === 0) {
    return (
      <div className="alerts alerts-clear">
        ✓ No active alerts — all batteries within thresholds.
      </div>
    )
  }
  if (!data) return null

  const critical = alarms.filter((a) => a.severity === 'critical').length

  return (
    <section className={`alerts ${critical ? 'has-critical' : ''}`}>
      <button className="alerts-head" onClick={() => setOpen((o) => !o)}>
        <span className="alerts-title">
          <span className="alerts-bell">🔔</span> Active Alerts
          <span className="alerts-count">{alarms.length}</span>
          {critical > 0 && <span className="alerts-count crit">{critical} critical</span>}
        </span>
        <span className="alerts-toggle">{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="alerts-list">
          {alarms.map((a) => {
            const meta = ALARM_META[a.code] ?? { label: a.code, unit: '' }
            return (
              <button
                key={a.id}
                className={`alert alert-${a.severity}`}
                onClick={() => onSelect(a.device_id)}
              >
                <span className={`sev-dot sev-${a.severity}`} />
                <span className="alert-dev">{a.device_id}</span>
                <span className="alert-desc">{meta.label}</span>
                <span className="alert-val">
                  {a.value != null ? `${a.value}${meta.unit}` : ''}
                </span>
                <span className="alert-time">{timeAgo(a.ts)}</span>
              </button>
            )
          })}
        </div>
      )}
    </section>
  )
}
