import { useState } from 'react'

function CheckGroup({ title, options, selected, onToggle }) {
  return (
    <div className="filter-group">
      <div className="filter-group-title">{title}</div>
      <div className="filter-checks">
        {options.map((o) => (
          <label key={o} className="filter-check">
            <input type="checkbox" checked={selected.includes(o)} onChange={() => onToggle(o)} />
            <span>{o}</span>
          </label>
        ))}
      </div>
    </div>
  )
}

// Advanced filters: multi-select site/company/equipment (checkboxes), an SoC
// range, and an active-alarms toggle. Value is a controlled object owned by App.
export default function FilterPanel({ options, value, onChange, onClear }) {
  const [open, setOpen] = useState(false)

  const activeCount =
    value.sites.length +
    value.companies.length +
    value.equipment.length +
    (value.hasAlarms ? 1 : 0) +
    (value.socMin !== '' ? 1 : 0) +
    (value.socMax !== '' ? 1 : 0)

  const toggle = (key, o) => {
    const arr = value[key]
    onChange({ ...value, [key]: arr.includes(o) ? arr.filter((x) => x !== o) : [...arr, o] })
  }

  return (
    <section className={`filter-panel ${activeCount ? 'has-active' : ''}`}>
      <button className="filter-toggle" onClick={() => setOpen((o) => !o)}>
        <span>⚙ Filters{activeCount ? ` · ${activeCount} active` : ''}</span>
        <span className="alerts-toggle">{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="filter-body">
          <CheckGroup title="Site" options={options.sites} selected={value.sites} onToggle={(o) => toggle('sites', o)} />
          <CheckGroup title="Company" options={options.companies} selected={value.companies} onToggle={(o) => toggle('companies', o)} />
          <CheckGroup title="Equipment" options={options.equipment} selected={value.equipment} onToggle={(o) => toggle('equipment', o)} />

          <div className="filter-group">
            <div className="filter-group-title">State of charge (%)</div>
            <div className="filter-range">
              <input type="number" min="0" max="100" placeholder="min"
                value={value.socMin} onChange={(e) => onChange({ ...value, socMin: e.target.value })} />
              <span>–</span>
              <input type="number" min="0" max="100" placeholder="max"
                value={value.socMax} onChange={(e) => onChange({ ...value, socMax: e.target.value })} />
            </div>
          </div>

          <div className="filter-group">
            <div className="filter-group-title">Alarms</div>
            <label className="filter-check">
              <input type="checkbox" checked={value.hasAlarms}
                onChange={(e) => onChange({ ...value, hasAlarms: e.target.checked })} />
              <span>Only packs with active alarms</span>
            </label>
          </div>

          <button className="pager-btn" disabled={!activeCount} onClick={onClear}>Clear filters</button>
        </div>
      )}
    </section>
  )
}
