import { useEffect, useRef, useState } from 'react'
import { fetchDevice, fetchReadings, fetchThresholds } from '../api'
import { usePolling } from '../usePolling'
import TrendChart from './TrendChart'

const MAX_POINTS = 240 // rolling window kept in the charts
const POLL_MS = 3000

const COLORS = { ok: '#2ecc71', warn: '#f4b740', crit: '#ff5c5c', soc: '#4aa8ff', volt: '#b98bff' }

function toPoint(r) {
  return {
    ts: r.ts,
    time: new Date(r.ts).toLocaleTimeString([], { hour12: false }),
    soc: r.soc,
    pack_voltage: r.pack_voltage,
  }
}

// Drill-down drawer: device detail + latest snapshot + live SoC/voltage trend
// charts. History loads once, then only NEW readings are fetched each poll
// (?since= cursor) and appended — the incremental-fetch pattern, not refetching
// the whole series every tick.
export default function DeviceDetail({ deviceId, onClose }) {
  const { data, error } = usePolling(() => fetchDevice(deviceId), POLL_MS, [deviceId])
  const [points, setPoints] = useState([])
  const [thresholds, setThresholds] = useState(null)
  const lastTs = useRef(null)

  useEffect(() => {
    fetchThresholds().then(setThresholds).catch(() => {})
  }, [])

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // history load + incremental delta polling
  useEffect(() => {
    let cancelled = false
    lastTs.current = null
    setPoints([])

    ;(async () => {
      try {
        const res = await fetchReadings(deviceId, { limit: MAX_POINTS })
        if (cancelled) return
        setPoints(res.readings.map(toPoint))
        lastTs.current = res.latest_ts
      } catch {
        /* surfaced via device fetch error */
      }
    })()

    const timer = setInterval(async () => {
      if (!lastTs.current || document.hidden) return
      try {
        const res = await fetchReadings(deviceId, { since: lastTs.current })
        if (cancelled || !res.readings.length) return
        lastTs.current = res.latest_ts
        setPoints((prev) => prev.concat(res.readings.map(toPoint)).slice(-MAX_POINTS))
      } catch {
        /* ignore transient poll errors */
      }
    }, POLL_MS)

    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [deviceId])

  const device = data?.device
  const status = data?.status
  const nominal = device ? Number(device.nominal_voltage) : null

  const socRef = thresholds
    ? [
        { y: thresholds.soc.warning, color: COLORS.warn, label: 'warn' },
        { y: thresholds.soc.critical, color: COLORS.crit, label: 'crit' },
      ]
    : []
  const voltRef =
    thresholds && nominal
      ? [
          { y: +(nominal * thresholds.pack_voltage_frac.warning).toFixed(1), color: COLORS.warn, label: 'warn' },
          { y: +(nominal * thresholds.pack_voltage_frac.critical).toFixed(1), color: COLORS.crit, label: 'crit' },
        ]
      : []

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <div>
            <h2>{device?.label ?? deviceId}</h2>
            <span className="card-devid">{deviceId}</span>
          </div>
          <button className="close" onClick={onClose} aria-label="Close">×</button>
        </div>

        {error && <div className="banner banner-error">{error}</div>}

        {device && (
          <div className="drawer-meta">
            <span>{device.model}</span>
            <span>· {device.site}</span>
            <span>· {device.cell_count} cells</span>
            <span>· {Number(device.nominal_voltage).toFixed(1)} V nominal</span>
            <span>· {Number(device.capacity_ah).toFixed(0)} Ah</span>
          </div>
        )}

        {status && (
          <div className="drawer-stats">
            <Stat label="State of charge" value={`${status.soc.toFixed(1)}%`} />
            <Stat label="Pack voltage" value={`${status.pack_voltage.toFixed(1)} V`} />
            <Stat label="Current" value={`${status.current_a.toFixed(0)} A`} />
            <Stat label="Temperature" value={`${status.temperature_c.toFixed(0)} °C`} />
            <Stat label="Status" value={status.status} className={`pill-${status.status}`} />
            <Stat label="Active alarms" value={status.active_alarms} />
          </div>
        )}

        <div className="charts">
          <TrendChart
            title="State of charge"
            data={points}
            dataKey="soc"
            unit="%"
            color={COLORS.soc}
            domain={[0, 100]}
            refLines={socRef}
          />
          <TrendChart
            title="Pack voltage"
            data={points}
            dataKey="pack_voltage"
            unit="V"
            color={COLORS.volt}
            refLines={voltRef}
          />
        </div>
        {points.length === 0 && <div className="drawer-placeholder">Loading history…</div>}
      </aside>
    </div>
  )
}

function Stat({ label, value, className = '' }) {
  return (
    <div className="dstat">
      <span className="dstat-label">{label}</span>
      <span className={`dstat-val ${className}`}>{value}</span>
    </div>
  )
}
