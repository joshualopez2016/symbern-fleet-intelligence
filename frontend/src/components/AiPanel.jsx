import { useState } from 'react'
import { aiSearch, aiBriefing } from '../api'

// Two AI features (FAU Trussed.ai, gpt-5.4):
//  - Ask AI: natural-language fleet search -> filtered devices (lifted to App)
//  - AI Briefing: a generated fleet-health summary in a modal
export default function AiPanel({ configured, active, onResult, onClear }) {
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [briefing, setBriefing] = useState(null) // {loading} | {text} | {error}

  async function search(e) {
    e.preventDefault()
    const query = q.trim()
    if (!query) return
    setBusy(true)
    setError(null)
    try {
      const res = await aiSearch(query)
      onResult({ ...res, query })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function doBriefing() {
    setBriefing({ loading: true })
    try {
      const res = await aiBriefing()
      setBriefing({ text: res.briefing })
    } catch (err) {
      setBriefing({ error: err.message })
    }
  }

  return (
    <section className="ai-panel">
      <form className="ai-bar" onSubmit={search}>
        <span className="ai-spark">✨</span>
        <input
          className="ai-input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={
            configured
              ? 'Ask AI:  “critical packs at Harbor Marine below 20%”'
              : 'AI disabled — add TRUSSED_API_KEY to .env to enable'
          }
          disabled={!configured || busy}
        />
        <button className="ai-btn" disabled={!configured || busy || !q.trim()}>
          {busy ? 'Thinking…' : 'Ask AI'}
        </button>
        <button type="button" className="ai-btn ghost" onClick={doBriefing} disabled={!configured || busy}>
          AI Briefing
        </button>
        {active && (
          <button type="button" className="ai-btn ghost" onClick={onClear}>
            Clear
          </button>
        )}
      </form>

      {error && <div className="banner banner-error">{error}</div>}
      {!configured && (
        <div className="ai-hint">
          AI features are off. Set <code>TRUSSED_API_KEY</code> in <code>.env</code> and restart the API.
        </div>
      )}

      {briefing && (
        <div className="drawer-backdrop" onClick={() => setBriefing(null)}>
          <div className="ai-modal" onClick={(e) => e.stopPropagation()}>
            <div className="ai-modal-head">
              <h3>✨ AI Fleet Briefing</h3>
              <button className="close" onClick={() => setBriefing(null)} aria-label="Close">×</button>
            </div>
            {briefing.loading && <div className="empty">Generating briefing…</div>}
            {briefing.error && <div className="banner banner-error">{briefing.error}</div>}
            {briefing.text && <p className="ai-briefing-text">{briefing.text}</p>}
          </div>
        </div>
      )}
    </section>
  )
}
