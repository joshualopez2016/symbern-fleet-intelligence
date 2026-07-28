// One battery at a glance. Border + status pill color-coded; SoC bar; key
// telemetry. Status comes from the backend (same thresholds the simulator uses).

function socClass(soc) {
  if (soc < 10) return 'soc-crit'
  if (soc < 25) return 'soc-warn'
  return 'soc-ok'
}

export default function DeviceCard({ device, onClick }) {
  const { device_id, label, soc, pack_voltage, current_a, temperature_c, status, active_alarms } =
    device
  const charging = current_a < 0

  return (
    <button className={`card card-${status}`} onClick={onClick}>
      <div className="card-head">
        <div className="card-id">
          <span className="card-label">{label}</span>
          <span className="card-devid">{device_id}</span>
        </div>
        <span className={`pill pill-${status}`}>{status}</span>
      </div>

      <div className="soc-row">
        <div className="soc-bar-track">
          <div
            className={`soc-bar-fill ${socClass(soc)}`}
            style={{ width: `${Math.max(0, Math.min(100, soc))}%` }}
          />
        </div>
        <span className="soc-pct">{soc.toFixed(0)}%</span>
      </div>

      <div className="metrics">
        <div className="metric">
          <span className="metric-val">{pack_voltage.toFixed(1)}<small>V</small></span>
          <span className="metric-key">pack</span>
        </div>
        <div className="metric">
          <span className="metric-val">
            {charging ? '▼' : '▲'} {Math.abs(current_a).toFixed(0)}<small>A</small>
          </span>
          <span className="metric-key">{charging ? 'charging' : 'load'}</span>
        </div>
        <div className="metric">
          <span className="metric-val">{temperature_c.toFixed(0)}<small>°C</small></span>
          <span className="metric-key">temp</span>
        </div>
      </div>

      {active_alarms > 0 && (
        <div className="card-alarm">⚠ {active_alarms} active alarm{active_alarms > 1 ? 's' : ''}</div>
      )}
    </button>
  )
}
