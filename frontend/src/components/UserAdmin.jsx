import { useEffect, useState } from 'react'
import { listUsers, createUser, updateUserRole, deleteUser } from '../api'

const ROLES = ['viewer', 'engineer', 'supervisor', 'administrator']

// Administrator-only user management: list users, add, change role, delete.
export default function UserAdmin({ me, onClose }) {
  const [users, setUsers] = useState([])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ email: '', password: '', role: 'viewer' })

  async function refresh() {
    try {
      const d = await listUsers()
      setUsers(d.users)
    } catch (e) {
      setError(e.message)
    }
  }
  useEffect(() => {
    refresh()
  }, [])

  async function add(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await createUser(form.email.trim(), form.password, form.role)
      setForm({ email: '', password: '', role: 'viewer' })
      await refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function changeRole(id, role) {
    setError(null)
    try {
      await updateUserRole(id, role)
      await refresh()
    } catch (e) {
      setError(e.message)
    }
  }

  async function remove(id) {
    setError(null)
    try {
      await deleteUser(id)
      await refresh()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="report-modal" onClick={(e) => e.stopPropagation()}>
        <div className="report-head">
          <div>
            <h2>👥 User Management</h2>
            <span className="report-sub">{users.length} users · administrator only</span>
          </div>
          <button className="close" onClick={onClose} aria-label="Close">×</button>
        </div>

        {error && <div className="banner banner-error">{error}</div>}

        <form className="user-add" onSubmit={add}>
          <input type="email" placeholder="email" value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          <input type="password" placeholder="password" value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <button className="note-btn" disabled={busy || !form.email || !form.password}>Add user</button>
        </form>

        <div className="report-scroll">
          <table className="report-table user-table">
            <thead>
              <tr><th>ID</th><th>Email</th><th>Role</th><th>Last login</th><th></th></tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td>{u.email}{u.email === me.email ? ' (you)' : ''}</td>
                  <td>
                    <select value={u.role} onChange={(e) => changeRole(u.id, e.target.value)}
                      disabled={u.email === me.email}>
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td>{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : '—'}</td>
                  <td>
                    <button className="note-link danger" onClick={() => remove(u.id)}
                      disabled={u.email === me.email}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
