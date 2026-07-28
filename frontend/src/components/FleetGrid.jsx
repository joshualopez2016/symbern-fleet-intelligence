import DeviceCard from './DeviceCard'

export default function FleetGrid({ devices, onSelect }) {
  return (
    <div className="grid">
      {devices.map((d) => (
        <DeviceCard key={d.device_id} device={d} onClick={() => onSelect(d.device_id)} />
      ))}
    </div>
  )
}
