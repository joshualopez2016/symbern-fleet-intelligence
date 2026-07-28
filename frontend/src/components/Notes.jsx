import { useEffect, useState } from 'react'
import { listNotes, createNote, updateNote, deleteNote } from '../api'

// Per-user notes on a pack — full CRUD (create / read / update / delete).
export default function Notes({ deviceId, canWrite = true }) {
  const [notes, setNotes] = useState([])
  const [draft, setDraft] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editText, setEditText] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    try {
      const d = await listNotes(deviceId)
      setNotes(d.notes)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    setEditingId(null)
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceId])

  async function add(e) {
    e.preventDefault()
    const b = draft.trim()
    if (!b) return
    setBusy(true)
    setError(null)
    try {
      await createNote(deviceId, b)
      setDraft('')
      await refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function saveEdit(id) {
    const b = editText.trim()
    if (!b) return
    setBusy(true)
    setError(null)
    try {
      await updateNote(id, b)
      setEditingId(null)
      await refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(id) {
    setBusy(true)
    setError(null)
    try {
      await deleteNote(id)
      await refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="notes">
      <h3 className="notes-title">Notes</h3>
      {error && <div className="banner banner-error">{error}</div>}

      {canWrite ? (
        <form className="note-add" onSubmit={add}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Add a note about this pack…"
            rows={2}
          />
          <button className="note-btn" disabled={busy || !draft.trim()}>Add</button>
        </form>
      ) : (
        <div className="notes-empty">Read-only — your role can’t add notes.</div>
      )}

      {notes.length === 0 && <div className="notes-empty">No notes yet.</div>}

      <ul className="note-list">
        {notes.map((n) => (
          <li key={n.id} className="note">
            {editingId === n.id ? (
              <div className="note-edit">
                <textarea value={editText} onChange={(e) => setEditText(e.target.value)} rows={2} />
                <div className="note-actions">
                  <button className="note-btn" onClick={() => saveEdit(n.id)} disabled={busy}>Save</button>
                  <button className="note-link" onClick={() => setEditingId(null)}>Cancel</button>
                </div>
              </div>
            ) : (
              <>
                <div className="note-body">{n.body}</div>
                <div className="note-meta">
                  <span>{new Date(n.updated_at).toLocaleString()}</span>
                  {canWrite && (
                    <div className="note-actions">
                      <button className="note-link" onClick={() => { setEditingId(n.id); setEditText(n.body) }}>Edit</button>
                      <button className="note-link danger" onClick={() => remove(n.id)}>Delete</button>
                    </div>
                  )}
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
