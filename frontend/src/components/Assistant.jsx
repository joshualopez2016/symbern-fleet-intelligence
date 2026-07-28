import { useEffect, useRef, useState } from 'react'
import { assistantChat, createTicket } from '../api'

const GREETING = {
  role: 'assistant',
  content:
    "Hi! I'm the Symbern assistant. Ask me how to use the dashboard — filtering, the query builder, production records, reports — or start a support ticket for IT or management.",
}

export default function Assistant() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([GREETING])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [ticketOpen, setTicketOpen] = useState(false)
  const [ticket, setTicket] = useState({ subject: '', category: 'IT', body: '' })
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages, open, ticketOpen])

  async function send(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    const next = [...messages, { role: 'user', content: text }]
    setMessages(next)
    setInput('')
    setBusy(true)
    setError(null)
    try {
      const { reply } = await assistantChat(next.filter((m) => m !== GREETING))
      setMessages((m) => [...m, { role: 'assistant', content: reply }])
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function submitTicket(e) {
    e.preventDefault()
    if (!ticket.subject.trim() || !ticket.body.trim()) return
    setBusy(true)
    setError(null)
    try {
      const t = await createTicket(ticket.subject.trim(), ticket.category, ticket.body.trim())
      setTicketOpen(false)
      setTicket({ subject: '', category: 'IT', body: '' })
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: `✅ Support ticket #${t.id} created (${t.category}, status: ${t.status}). Someone will follow up.` },
      ])
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button className="assistant-fab" onClick={() => setOpen(true)} title="Open assistant">
        💬 Assistant
      </button>
    )
  }

  return (
    <div className="assistant-panel">
      <div className="assistant-head">
        <span>💬 Symbern Assistant</span>
        <button className="close" onClick={() => setOpen(false)} aria-label="Close">×</button>
      </div>

      <div className="assistant-msgs" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={`amsg amsg-${m.role}`}>{m.content}</div>
        ))}
        {busy && !ticketOpen && <div className="amsg amsg-assistant amsg-typing">…</div>}
        {error && <div className="banner banner-error">{error}</div>}
      </div>

      {ticketOpen ? (
        <form className="ticket-form" onSubmit={submitTicket}>
          <div className="ticket-row">
            <input placeholder="Subject" value={ticket.subject}
              onChange={(e) => setTicket({ ...ticket, subject: e.target.value })} required />
            <select value={ticket.category} onChange={(e) => setTicket({ ...ticket, category: e.target.value })}>
              <option value="IT">IT</option>
              <option value="Management">Management</option>
              <option value="Other">Other</option>
            </select>
          </div>
          <textarea placeholder="Describe the issue or request…" rows={3} value={ticket.body}
            onChange={(e) => setTicket({ ...ticket, body: e.target.value })} required />
          <div className="ticket-actions">
            <button className="ai-btn" disabled={busy}>Submit ticket</button>
            <button type="button" className="pager-btn" onClick={() => setTicketOpen(false)}>Cancel</button>
          </div>
        </form>
      ) : (
        <>
          <form className="assistant-input" onSubmit={send}>
            <input value={input} onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about the app…" disabled={busy} />
            <button className="ai-btn" disabled={busy || !input.trim()}>Send</button>
          </form>
          <button className="ticket-cta" onClick={() => setTicketOpen(true)}>🎫 Start a support ticket</button>
        </>
      )}
    </div>
  )
}
