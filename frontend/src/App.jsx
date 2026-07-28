import { useEffect, useState } from 'react'
import { fetchFleet, fetchFleetSummary, fetchMe, logout, getAuthToken, aiStatus, exportFleet } from './api'
import { usePolling } from './usePolling'
import FleetGrid from './components/FleetGrid'
import DeviceDetail from './components/DeviceDetail'
import AlertsPanel from './components/AlertsPanel'
import AiPanel from './components/AiPanel'
import DailyReport from './components/DailyReport'
import Login from './components/Login'

const POLL_MS = 3000
const PAGE = 200 // bounded worst-first page — response size stays flat as the fleet grows

export default function App() {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    let cancelled = false
    const onUnauth = () => setUser(null)
    window.addEventListener('bms-unauthorized', onUnauth)
    if (getAuthToken()) {
      fetchMe()
        .then((u) => !cancelled && setUser(u))
        .catch(() => !cancelled && setUser(null))
        .finally(() => !cancelled && setChecking(false))
    } else {
      setChecking(false)
    }
    return () => {
      cancelled = true
      window.removeEventListener('bms-unauthorized', onUnauth)
    }
  }, [])

  async function handleLogout() {
    await logout()
    setUser(null)
  }

  if (checking) {
    return (
      <div className="app">
        <div className="empty">Loading…</div>
      </div>
    )
  }
  if (!user) return <Login onLogin={setUser} />
  return <Dashboard user={user} onLogout={handleLogout} />
}

function Dashboard({ user, onLogout }) {
  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState(null)
  const [aiResult, setAiResult] = useState(null)
  const [aiConfigured, setAiConfigured] = useState(false)
  const [showReport, setShowReport] = useState(false)

  // debounce the search box so typing doesn't fire a request per keystroke
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search])

  // reset paging + clear any AI search when the normal filter/search changes
  useEffect(() => {
    setOffset(0)
    setAiResult(null)
  }, [statusFilter, debouncedSearch])

  useEffect(() => {
    aiStatus().then((s) => setAiConfigured(s.configured)).catch(() => {})
  }, [])

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
  const gridDevices = aiResult ? aiResult.devices : devices
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
          <div className="user-chip">
            <span className="user-email">{user.email}</span>
            <span className={`user-role role-${user.role}`}>{user.role}</span>
            <button className="logout-btn" onClick={onLogout}>Log out</button>
          </div>
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

      <AiPanel
        configured={aiConfigured}
        active={!!aiResult}
        onResult={setAiResult}
        onClear={() => setAiResult(null)}
      />

      <AlertsPanel onSelect={setSelected} />

      <div className="fleet-meta">
        {aiResult ? (
          <span className="ai-result-meta">
            ✨ {aiResult.explanation || 'AI search'} · <strong>{aiResult.count}</strong>{' '}
            match{aiResult.count === 1 ? '' : 'es'}
          </span>
        ) : matched > 0 ? (
          <span>
            Showing <strong>{pageStart}–{pageEnd}</strong> of <strong>{matched}</strong>
            {statusFilter !== 'all' ? ` ${statusFilter}` : ''} device
            {matched === 1 ? '' : 's'} · worst first
          </span>
        ) : (
          <span />
        )}
        <div className="fleet-actions">
          <button className="pager-btn" onClick={() => exportFleet('csv', { status: statusFilter, q: debouncedSearch })}>⬇ CSV</button>
          <button className="pager-btn" onClick={() => exportFleet('xlsx', { status: statusFilter, q: debouncedSearch })}>⬇ Excel</button>
          <button className="pager-btn" onClick={() => setShowReport(true)}>📄 Daily Report</button>
          {!aiResult && matched > PAGE && (
            <>
              <button className="pager-btn" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}>‹ Prev</button>
              <button className="pager-btn" disabled={pageEnd >= matched} onClick={() => setOffset((o) => o + PAGE)}>Next ›</button>
            </>
          )}
        </div>
      </div>

      <main className="content">
        {loading && !aiResult && !devices.length ? (
          <div className="empty">Loading fleet…</div>
        ) : gridDevices.length ? (
          <FleetGrid devices={gridDevices} onSelect={setSelected} />
        ) : (
          <div className="empty">
            {aiResult ? 'No devices match your AI search.' : 'No devices match this filter.'}
          </div>
        )}
      </main>

      {selected && (
        <DeviceDetail deviceId={selected} onClose={() => setSelected(null)} />
      )}
      {showReport && <DailyReport onClose={() => setShowReport(false)} />}
    </div>
  )
}
