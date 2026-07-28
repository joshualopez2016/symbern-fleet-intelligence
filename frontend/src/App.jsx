import { useEffect, useState } from 'react'
import { fetchFleet, fetchFleetSummary } from './api'
import { usePolling } from './usePolling'
import FleetGrid from './components/FleetGrid'
import DeviceDetail from './components/DeviceDetail'
import AlertsPanel from './components/AlertsPanel'

const POLL_MS = 3000
const PAGE = 200 // bounded worst-first page — response size stays flat as the fleet grows

export default function App() {
  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState(null)

  // debounce the search box so typing doesn't fire a request per keystroke
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search])

  // reset paging when the filter or search changes
  useEffect(() => {
    setOffset(0)
  }, [statusFilter, debouncedSearch])

  // Whole-fleet tallies — one cheap aggregate, independent of paging.
  const { data: summary } = usePolling(fetchFleetSummary, POLL_MS, [])

  // The grid page — server does the filtering, worst-first sort, and pagination,
  // so the payload is capped at PAGE rows no matter how large the fleet is.
  const { data: fleet, error, loading } = usePolling(
    () =>
      fetchFleet({
        status: statusFilter === 'all' ? undefined : statusFilter,
        q: debouncedSearch || undefined,
        limit: PAGE,
        offset,
      }),
    POLL_MS,
    [statusFilter, debouncedSearch, offset],
  )

  const devices = fleet?.devices ?? []
  const matched = fleet?.total ?? 0
  const counts = {
    all: summary?.total ?? 0,
    ok: summary?.ok ?? 0,
    warning: summary?.warning ?? 0,
    critical: summary?.critical ?? 0,
  }

  const lastUpdated = devices.length
    ? new Date(
        devices.reduce((m, d) => (d.ts > m ? d.ts : m), devices[0].ts),
      ).toLocaleTimeString()
    : null

  const pageStart = matched === 0 ? 0 : offset + 1
  const pageEnd = Math.min(offset + PAGE, matched)

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">⚡</span>
          <div>
            <h1>BMS Fleet Dashboard</h1>
            <p className="subtitle">Battery telemetry · live monitoring</p>
          </div>
        </div>
        <div className="topbar-status">
          {error ? (
            <span className="conn conn-bad">● disconnected</span>
          ) : (
            <span className="conn conn-ok">● live</span>
          )}
          {lastUpdated && <span className="updated">updated {lastUpdated}</span>}
        </div>
      </header>

      {error && (
        <div className="banner banner-error">
          Cannot reach the API ({error}). Is the backend running on :8000?
        </div>
      )}

      <section className="summary">
        {['all', 'critical', 'warning', 'ok'].map((s) => (
          <button
            key={s}
            className={`stat stat-${s} ${statusFilter === s ? 'active' : ''}`}
            onClick={() => setStatusFilter(s)}
          >
            <span className="stat-num">{counts[s] ?? 0}</span>
            <span className="stat-label">{s === 'all' ? 'Total' : s}</span>
          </button>
        ))}
        <div className="search-wrap">
          <input
            className="search"
            placeholder="Search device id or label…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </section>

      <AlertsPanel onSelect={setSelected} />

      <div className="fleet-meta">
        {matched > 0 ? (
          <span>
            Showing <strong>{pageStart}–{pageEnd}</strong> of <strong>{matched}</strong>
            {statusFilter !== 'all' ? ` ${statusFilter}` : ''} device
            {matched === 1 ? '' : 's'} · worst first
          </span>
        ) : (
          <span />
        )}
        {matched > PAGE && (
          <div className="pager">
            <button disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}>
              ‹ Prev
            </button>
            <button disabled={pageEnd >= matched} onClick={() => setOffset((o) => o + PAGE)}>
              Next ›
            </button>
          </div>
        )}
      </div>

      <main className="content">
        {loading && !devices.length ? (
          <div className="empty">Loading fleet…</div>
        ) : devices.length ? (
          <FleetGrid devices={devices} onSelect={setSelected} />
        ) : (
          <div className="empty">No devices match this filter.</div>
        )}
      </main>

      {selected && (
        <DeviceDetail deviceId={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
