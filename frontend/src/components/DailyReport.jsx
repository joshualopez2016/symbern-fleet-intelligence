import { useState } from 'react'
import { usePolling } from '../usePolling'
import { fetchDailyReport, exportDailyReport } from '../api'

// Daily per-pack report in a modal: a wide table with CSV/Excel export and
// browser print (Save-as-PDF). The .report-print wrapper is isolated for printing.
export default function DailyReport({ onClose }) {
  const { data, error } = usePolling(() => fetchDailyReport(), 0 || 60000, [])
  const [busy, setBusy] = useState(null)

  const rows = data?.rows ?? []
  const headers = rows.length ? Object.keys(rows[0]) : []

  async function doExport(fmt) {
    setBusy(fmt)
    try {
      await exportDailyReport(fmt, data?.date)
    } catch {
      /* ignore; surfaced elsewhere */
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="report-modal" onClick={(e) => e.stopPropagation()}>
        <div className="report-head">
          <div>
            <h2>Daily Pack Report</h2>
            <span className="report-sub">{data?.date ?? '…'} · {rows.length} packs</span>
          </div>
          <div className="report-actions">
            <button className="pager-btn" disabled={busy || !rows.length} onClick={() => doExport('csv')}>
              {busy === 'csv' ? '…' : '⬇ CSV'}
            </button>
            <button className="pager-btn" disabled={busy || !rows.length} onClick={() => doExport('xlsx')}>
              {busy === 'xlsx' ? '…' : '⬇ Excel'}
            </button>
            <button className="pager-btn" disabled={!rows.length} onClick={() => window.print()}>
              🖨 Print / PDF
            </button>
            <button className="close" onClick={onClose} aria-label="Close">×</button>
          </div>
        </div>

        {error && <div className="banner banner-error">{error}</div>}

        <div className="report-print">
          <h3 className="report-print-title">Daily Pack Report — {data?.date ?? ''}</h3>
          <div className="report-scroll">
            <table className="report-table">
              <thead>
                <tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    {headers.map((h) => <td key={h}>{String(r[h] ?? '')}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!rows.length && !error && <div className="empty">Loading report…</div>}
        </div>
      </div>
    </div>
  )
}
