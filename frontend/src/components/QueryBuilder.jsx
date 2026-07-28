import { useEffect, useMemo, useState } from 'react'
import { querySources, queryRun } from '../api'

const OP_LABELS = {
  eq: '=', ne: '≠', lt: '<', le: '≤', gt: '>', ge: '≥',
  contains: 'contains', starts_with: 'starts with',
  before: 'before', after: 'after', on: 'on date',
}

function csvEscape(v) {
  const s = v == null ? '' : String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

// No-code query builder: pick a data source, add conditions, choose columns,
// sort, and run. The backend turns the structured spec into parameterized SQL.
export default function QueryBuilder({ onClose }) {
  const [sources, setSources] = useState(null)
  const [source, setSource] = useState('')
  const [columns, setColumns] = useState([])
  const [filters, setFilters] = useState([])
  const [sort, setSort] = useState({ field: '', dir: 'asc' })
  const [limit, setLimit] = useState(100)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    querySources()
      .then((s) => {
        setSources(s)
        const first = Object.keys(s)[0]
        if (first) selectSource(s, first)
      })
      .catch((e) => setError(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const fields = useMemo(
    () => (sources && source ? sources[source].fields : []),
    [sources, source],
  )
  const fieldDef = (name) => fields.find((f) => f.name === name)

  function selectSource(allSources, name) {
    const s = allSources[name]
    setSource(name)
    setColumns(s.fields.map((f) => f.name))
    setFilters([])
    setSort(s.default_sort || { field: s.fields[0]?.name, dir: 'asc' })
    setResult(null)
    setError(null)
  }

  function addFilter() {
    const f = fields[0]
    if (!f) return
    setFilters((prev) => [...prev, { field: f.name, op: f.ops[0], value: '' }])
  }
  function updateFilter(i, patch) {
    setFilters((prev) => prev.map((f, idx) => (idx === i ? { ...f, ...patch } : f)))
  }
  function changeFilterField(i, name) {
    const fd = fieldDef(name)
    updateFilter(i, { field: name, op: fd.ops[0], value: '' })
  }
  function removeFilter(i) {
    setFilters((prev) => prev.filter((_, idx) => idx !== i))
  }
  function toggleColumn(name) {
    setColumns((prev) => (prev.includes(name) ? prev.filter((c) => c !== name) : [...prev, name]))
  }

  async function run() {
    setLoading(true)
    setError(null)
    try {
      const spec = {
        source,
        columns,
        filters: filters.filter((f) => f.value !== '' && f.value != null),
        sort,
        limit,
      }
      setResult(await queryRun(spec))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function downloadCsv() {
    if (!result) return
    const csv = [
      result.columns.join(','),
      ...result.rows.map((r) => result.columns.map((c) => csvEscape(r[c])).join(',')),
    ].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${source}_query.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  function ValueInput({ f, i }) {
    const fd = fieldDef(f.field)
    if (!fd) return null
    if (fd.type === 'enum') {
      return (
        <select value={f.value} onChange={(e) => updateFilter(i, { value: e.target.value })}>
          <option value="">—</option>
          {fd.values.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
      )
    }
    if (fd.type === 'boolean') {
      return (
        <select value={f.value} onChange={(e) => updateFilter(i, { value: e.target.value })}>
          <option value="">—</option>
          <option value="true">true</option>
          <option value="false">false</option>
        </select>
      )
    }
    const type = fd.type === 'number' ? 'number' : fd.type === 'timestamp' ? 'date' : 'text'
    return (
      <input type={type} value={f.value}
        onChange={(e) => updateFilter(i, { value: e.target.value })} placeholder="value" />
    )
  }

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="qb-modal" onClick={(e) => e.stopPropagation()}>
        <div className="report-head">
          <div>
            <h2>🔎 Query Builder</h2>
            <span className="report-sub">Build a query without writing SQL</span>
          </div>
          <button className="close" onClick={onClose} aria-label="Close">×</button>
        </div>

        {error && <div className="banner banner-error">{error}</div>}
        {!sources && !error && <div className="empty">Loading…</div>}

        {sources && (
          <div className="qb-body">
            <div className="qb-controls">
              <div className="qb-row">
                <label className="qb-label">Data source</label>
                <select value={source} onChange={(e) => selectSource(sources, e.target.value)}>
                  {Object.entries(sources).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                </select>
              </div>

              <div className="qb-section">
                <div className="qb-section-head">
                  <span>Conditions</span>
                  <button className="pager-btn" onClick={addFilter}>+ Add</button>
                </div>
                {filters.length === 0 && <div className="qb-hint">No conditions — returns all rows.</div>}
                {filters.map((f, i) => (
                  <div key={i} className="qb-filter">
                    <select value={f.field} onChange={(e) => changeFilterField(i, e.target.value)}>
                      {fields.map((fd) => <option key={fd.name} value={fd.name}>{fd.label}</option>)}
                    </select>
                    <select value={f.op} onChange={(e) => updateFilter(i, { op: e.target.value })}>
                      {(fieldDef(f.field)?.ops || []).map((op) => (
                        <option key={op} value={op}>{OP_LABELS[op] || op}</option>
                      ))}
                    </select>
                    <ValueInput f={f} i={i} />
                    <button className="qb-x" onClick={() => removeFilter(i)} aria-label="Remove">×</button>
                  </div>
                ))}
              </div>

              <div className="qb-section">
                <div className="qb-section-head"><span>Columns</span></div>
                <div className="filter-checks qb-cols">
                  {fields.map((fd) => (
                    <label key={fd.name} className="filter-check">
                      <input type="checkbox" checked={columns.includes(fd.name)} onChange={() => toggleColumn(fd.name)} />
                      <span>{fd.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="qb-row qb-inline">
                <div>
                  <label className="qb-label">Sort by</label>
                  <select value={sort.field} onChange={(e) => setSort({ ...sort, field: e.target.value })}>
                    {fields.map((fd) => <option key={fd.name} value={fd.name}>{fd.label}</option>)}
                  </select>
                  <select value={sort.dir} onChange={(e) => setSort({ ...sort, dir: e.target.value })}>
                    <option value="asc">asc</option>
                    <option value="desc">desc</option>
                  </select>
                </div>
                <div>
                  <label className="qb-label">Limit</label>
                  <input type="number" min="1" max="1000" value={limit}
                    onChange={(e) => setLimit(e.target.value)} className="qb-limit" />
                </div>
                <button className="ai-btn" onClick={run} disabled={loading || !columns.length}>
                  {loading ? 'Running…' : 'Run query'}
                </button>
              </div>
            </div>

            {result && (
              <div className="qb-result">
                <div className="qb-result-head">
                  <span>{result.count} rows</span>
                  <button className="pager-btn" onClick={downloadCsv} disabled={!result.rows.length}>⬇ CSV</button>
                </div>
                <pre className="qb-sql">{result.sql}</pre>
                <div className="report-scroll">
                  <table className="report-table">
                    <thead>
                      <tr>{result.columns.map((c) => <th key={c}>{c}</th>)}</tr>
                    </thead>
                    <tbody>
                      {result.rows.map((r, i) => (
                        <tr key={i}>{result.columns.map((c) => <td key={c}>{String(r[c] ?? '')}</td>)}</tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
