import { useEffect, useState } from 'react'
import { fetchFleet, fetchFleetSummary, fetchMe, logout, getAuthToken, aiStatus, exportFleet, fetchFilterOptions } from './api'
import { usePolling } from './usePolling'
import { useFleetSocket } from './useFleetSocket'
import FleetGrid from './components/FleetGrid'
import DeviceDetail from './components/DeviceDetail'
import AlertsPanel from './components/AlertsPanel'
import AiPanel from './components/AiPanel'
import DailyReport from './components/DailyReport'
import FilterPanel from './components/FilterPanel'
import QueryBuilder from './components/QueryBuilder'
import UserAdmin from './components/UserAdmin'
import Login from './components/Login'

const POLL_MS = 3000
const PAGE = 200 // bounded worst-first page — response size stays flat as the fleet grows
const DEFAULT_FILTERS = { sites: [], companies: [], equipment: [], socMin: '', socMax: '', hasAlarms: false }

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
  const [showQuery, setShowQuery] = useState(false)
  const [showUsers, setShowUsers] = useState(false)
  const isAdmin = user.role === 'administrator'
  const canWriteNotes = ['engineer', 'supervisor', 'administrator'].includes(user.role)
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [filterOptions, setFilterOptions] = useState({ sites: [], companies: [], equipment: [] })

  // debounce the search box so typing doesn't fire a request per keystroke
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search])

  // reset paging + clear any AI search when the normal filter/search changes
  useEffect(() => {
    setOffset(0)
    setAiResult(null)
  }, [statusFilter, debouncedSearch, filters])

  useEffect(() => {
    aiStatus().then((s) => setAiConfigured(s.configured)).catch(() => {})
    fetchFilterOptions().then(setFilterOptions).catch(() => {})
  }, [])

  // Shared filter params for both the grid fetch and the exports.
  const fleetParams = {
    status: statusFilter === 'all' ? undefined : statusFilter,
    sites: filters.sites.length ? filters.sites.join(',') : undefined,
    companies: filters.companies.length ? filters.companies.join(',') : undefined,
    equipment: filters.equipment.length ? filters.equipment.join(',') : undefined,
    soc_min: filters.socMin !== '' ? filters.socMin : undefined,
    soc_max: filters.socMax !== '' ? filters.socMax : undefined,
    has_alarms: filters.hasAlarms ? 'true' : undefined,
    q: debouncedSearch || undefined,
  }

  // Whole-fleet tallies — one cheap aggregate, independent of paging.
  const { data: summary, refresh: refreshSummary } = usePolling(fetchFleetSummary, POLL_MS, [])

  // The grid page — server does the filtering, worst-first sort, and pagination,
  // so the payload is capped at PAGE rows no matter how large the fleet is.
  const { data: fleet, error, loading, refresh: refreshFleet } = usePolling(
    () => fetchFleet({ ...fleetParams, limit: PAGE, offset }),
    POLL_MS,
    [statusFilter, debouncedSearch, offset, filters],
  )

  const refreshNow = () => {
    refreshFleet()
    refreshSummary()
  }

  // Realtime feed. Drives the default view; HTTP takes over when the user
  // filters/searches/paginates (which the pushed snapshot doesn't scope).
  const { connected: wsConnected, snapshot: wsSnap } = useFleetSocket(true)

  const hasAdvancedFilters =
    filters.sites.length || filters.companies.length || filters.equipment.length ||
    filters.socMin !== '' || filters.socMax !== '' || filters.hasAlarms
  const isDefaultView =
    statusFilter === 'all' && !debouncedSearch && offset === 0 && !aiResult && !hasAdvancedFilters
  const useLive = wsConnected && !!wsSnap && isDefaultView

  const liveSummary = wsConnected && wsSnap ? wsSnap.summary : summary
  const effectiveDevices = useLive ? wsSnap.devices : (fleet?.devices ?? [])
  const gridDevices = aiResult
    ? aiResult.devices
    : useLive
      ? wsSnap.devices.slice(0, PAGE)
      : effectiveDevices
  const matched = useLive ? (wsSnap.summary?.total ?? wsSnap.devices.length) : (fleet?.total ?? 0)
  const counts = {
    all: liveSummary?.total ?? 0,
    ok: liveSummary?.ok ?? 0,
    warning: liveSummary?.warning ?? 0,
    critical: liveSummary?.critical ?? 0,
  }

  const lastUpdated = effectiveDevices.length
    ? new Date(
        effectiveDevices.reduce((m, d) => (d.ts > m ? d.ts : m), effectiveDevices[0].ts),
      ).toLocaleTimeString()
    : null

  const pageStart = matched === 0 ? 0 : offset + 1
  const pageEnd = Math.min(offset + PAGE, matched)

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">S</span>
          <div>
            <h1>Symbern <span className="brand-tag">Fleet Intelligence</span></h1>
            <p className="subtitle">Turning fleet data into live decisions</p>
          </div>
        </div>
        <div className="topbar-status">
          {wsConnected ? (
            <span className="conn conn-live">⚡ Realtime</span>
          ) : error ? (
            <span className="conn conn-bad">● disconnected</span>
          ) : (
            <span className="conn conn-ok">● polling</span>
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

      <FilterPanel
        options={filterOptions}
        value={filters}
        onChange={setFilters}
        onClear={() => setFilters(DEFAULT_FILTERS)}
      />

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
          <button className="pager-btn" onClick={refreshNow} title="Refresh now">↻ Refresh</button>
          <button className="pager-btn" onClick={() => exportFleet('csv', fleetParams)}>⬇ CSV</button>
          <button className="pager-btn" onClick={() => exportFleet('xlsx', fleetParams)}>⬇ Excel</button>
          <button className="pager-btn" onClick={() => setShowReport(true)}>📄 Daily Report</button>
          <button className="pager-btn" onClick={() => setShowQuery(true)}>🔎 Query Builder</button>
          {isAdmin && <button className="pager-btn" onClick={() => setShowUsers(true)}>👥 Users</button>}
          {!aiResult && matched > PAGE && (
            <>
              <button className="pager-btn" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}>‹ Prev</button>
              <button className="pager-btn" disabled={pageEnd >= matched} onClick={() => setOffset((o) => o + PAGE)}>Next ›</button>
            </>
          )}
        </div>
      </div>

      <main className="content">
        {loading && !aiResult && !useLive && !gridDevices.length ? (
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
        <DeviceDetail deviceId={selected} canWriteNotes={canWriteNotes} onClose={() => setSelected(null)} />
      )}
      {showUsers && <UserAdmin me={user} onClose={() => setShowUsers(false)} />}
      {showReport && <DailyReport onClose={() => setShowReport(false)} />}
      {showQuery && <QueryBuilder onClose={() => setShowQuery(false)} />}

      <footer className="app-footer">
        <span className="foot-brand">Symbern</span> — Batteries. Equipment. Intelligence.
        <span className="foot-sep">·</span> We power modern logistics.
      </footer>
    </div>
  )
}
