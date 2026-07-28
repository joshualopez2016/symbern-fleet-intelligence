import { useEffect, useMemo, useState } from 'react'
import {
  productionRecords, productionSummary, productionSerial, productionSearch,
  productionFilterOptions, exportProduction,
} from '../api'

const PAGE = 100

function Tile({ label, value, tone }) {
  return (
    <div className={`ptile ptile-${tone || 'neutral'}`}>
      <span className="ptile-val">{value}</span>
      <span className="ptile-label">{label}</span>
    </div>
  )
}

// Serial drill-down modal: full chronological test history for one unit.
function SerialHistory({ serial, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    productionSerial(serial).then(setData).catch((e) => setError(e.message))
  }, [serial])
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="report-modal" onClick={(e) => e.stopPropagation()}>
        <div className="report-head">
          <div>
            <h2>Serial {serial}</h2>
            {data && (
              <span className="report-sub">
                {data.product} · {data.part_number} · {data.tests} tests ·
                {' '}{data.passed} pass / {data.failed} fail
              </span>
            )}
          </div>
          <button className="close" onClick={onClose} aria-label="Close">×</button>
        </div>
        {error && <div className="banner banner-error">{error}</div>}
        <div className="report-scroll">
          <table className="report-table">
            <thead>
              <tr><th>Time</th><th>Station</th><th>Fixture</th><th>Operator</th><th>Test</th><th>Result</th><th>Measured</th><th>Limits</th><th>Failure</th></tr>
            </thead>
            <tbody>
              {(data?.records || []).map((r) => (
                <tr key={r.id}>
                  <td>{new Date(r.ts).toLocaleString()}</td>
                  <td>{r.station}</td>
                  <td>{r.fixture}</td>
                  <td>{r.operator}</td>
                  <td>{r.test_parameter}</td>
                  <td><span className={`res res-${r.result.toLowerCase()}`}>{r.result}</span></td>
                  <td>{r.measured_value}</td>
                  <td>{r.limit_low}–{r.limit_high}</td>
                  <td>{r.failure_reason || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default function Production() {
  const [options, setOptions] = useState(null)
  const [summary, setSummary] = useState(null)
  const [summaryDate, setSummaryDate] = useState('')
  const [filters, setFilters] = useState({
    product: '', station: '', fixture: '', test_parameter: '', result: '',
    serial: '', from: '', to: '',
  })
  const [records, setRecords] = useState({ total: 0, records: [] })
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [searchResult, setSearchResult] = useState(null)
  const [selectedSerial, setSelectedSerial] = useState(null)

  useEffect(() => {
    productionFilterOptions().then(setOptions).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    productionSummary(summaryDate || undefined).then(setSummary).catch(() => {})
  }, [summaryDate])

  const queryParams = useMemo(
    () => ({ ...filters, limit: PAGE, offset }),
    [filters, offset],
  )

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    productionRecords(queryParams)
      .then((d) => { if (!cancelled) { setRecords(d); setError(null) } })
      .catch((e) => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [queryParams])

  function setFilter(patch) {
    setOffset(0)
    setSearchResult(null)
    setFilters((f) => ({ ...f, ...patch }))
  }

  async function runSearch(e) {
    e.preventDefault()
    const q = search.trim()
    if (!q) { setSearchResult(null); return }
    try {
      setSearchResult(await productionSearch(q))
    } catch (err) {
      setError(err.message)
    }
  }

  const shown = searchResult ? searchResult.records : records.records
  const total = searchResult ? searchResult.count : records.total
  const pageEnd = Math.min(offset + PAGE, records.total)

  return (
    <div className="production">
      <section className="psummary">
        <div className="psummary-head">
          <h2>Daily Production Summary</h2>
          <input type="date" value={summaryDate}
            onChange={(e) => setSummaryDate(e.target.value)}
            title="Pick a day (defaults to latest)" />
        </div>
        {summary && (
          <>
            <div className="ptiles">
              <Tile label="Tested" value={summary.total_tested} tone="neutral" />
              <Tile label="Passed" value={summary.passed} tone="ok" />
              <Tile label="Failed" value={summary.failed} tone="crit" />
              <Tile label="Pass %" value={`${summary.pass_pct}%`} tone="ok" />
              <Tile label="Fail %" value={`${summary.fail_pct}%`} tone="crit" />
            </div>
            <div className="pmostfailed">
              <span>Most failed —</span>
              <b>Product:</b> {summary.most_failed_product?.name ?? '—'}
              {summary.most_failed_product && ` (${summary.most_failed_product.fails})`}
              <b>Fixture:</b> {summary.most_failed_fixture?.name ?? '—'}
              {summary.most_failed_fixture && ` (${summary.most_failed_fixture.fails})`}
              <b>Station:</b> {summary.most_failed_station?.name ?? '—'}
              {summary.most_failed_station && ` (${summary.most_failed_station.fails})`}
            </div>
          </>
        )}
      </section>

      <form className="psearch" onSubmit={runSearch}>
        <span className="ai-spark">🔎</span>
        <input className="ai-input" value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Universal search: serial, part #, product, station, fixture, operator…" />
        <button className="pager-btn">Search</button>
        {searchResult && <button type="button" className="pager-btn" onClick={() => { setSearch(''); setSearchResult(null) }}>Clear</button>}
      </form>

      {error && <div className="banner banner-error">{error}</div>}

      {!searchResult && options && (
        <div className="pfilters">
          <Select label="Product" value={filters.product} opts={options.products} onChange={(v) => setFilter({ product: v })} />
          <Select label="Station" value={filters.station} opts={options.stations} onChange={(v) => setFilter({ station: v })} />
          <Select label="Fixture" value={filters.fixture} opts={options.fixtures} onChange={(v) => setFilter({ fixture: v })} />
          <Select label="Test" value={filters.test_parameter} opts={options.test_parameters} onChange={(v) => setFilter({ test_parameter: v })} />
          <Select label="Result" value={filters.result} opts={['Pass', 'Fail']} onChange={(v) => setFilter({ result: v })} />
          <label className="pfield"><span>Serial</span>
            <input value={filters.serial} onChange={(e) => setFilter({ serial: e.target.value })} placeholder="SYM-…" />
          </label>
          <label className="pfield"><span>From</span>
            <input type="date" value={filters.from} onChange={(e) => setFilter({ from: e.target.value })} />
          </label>
          <label className="pfield"><span>To</span>
            <input type="date" value={filters.to} onChange={(e) => setFilter({ to: e.target.value })} />
          </label>
          <div className="pfield">
            <span>Export</span>
            <div className="fleet-actions">
              <button className="pager-btn" onClick={() => exportProduction('csv', filters)}>⬇ CSV</button>
              <button className="pager-btn" onClick={() => exportProduction('xlsx', filters)}>⬇ Excel</button>
            </div>
          </div>
        </div>
      )}

      <div className="fleet-meta">
        <span>
          {searchResult
            ? `🔎 ${searchResult.count} match${searchResult.count === 1 ? '' : 'es'} for “${searchResult.query}”`
            : `${records.total} records`}
          {!searchResult && records.total > PAGE && ` · showing ${offset + 1}–${pageEnd}`}
        </span>
        {!searchResult && records.total > PAGE && (
          <div className="pager">
            <button className="pager-btn" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}>‹ Prev</button>
            <button className="pager-btn" disabled={pageEnd >= records.total} onClick={() => setOffset((o) => o + PAGE)}>Next ›</button>
          </div>
        )}
      </div>

      <div className="report-scroll ptable-wrap">
        <table className="report-table">
          <thead>
            <tr><th>Time</th><th>Serial</th><th>Product</th><th>Part #</th><th>Station</th><th>Fixture</th><th>Operator</th><th>Test</th><th>Result</th><th>Measured</th></tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.ts).toLocaleString()}</td>
                <td><button className="serial-link" onClick={() => setSelectedSerial(r.serial_number)}>{r.serial_number}</button></td>
                <td>{r.product}</td>
                <td>{r.part_number}</td>
                <td>{r.station}</td>
                <td>{r.fixture}</td>
                <td>{r.operator}</td>
                <td>{r.test_parameter}</td>
                <td><span className={`res res-${r.result.toLowerCase()}`}>{r.result}</span></td>
                <td>{r.measured_value}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && !shown.length && <div className="empty">Loading…</div>}
        {!loading && !shown.length && <div className="empty">No records match.</div>}
      </div>

      {selectedSerial && <SerialHistory serial={selectedSerial} onClose={() => setSelectedSerial(null)} />}
    </div>
  )
}

function Select({ label, value, opts, onChange }) {
  return (
    <label className="pfield">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  )
}
