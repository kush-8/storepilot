export default function TicketFilters({ filters, stores, onChange, onRefresh, disabled = false }) {
  function filter(key, value) { onChange({ ...filters, [key]: value || undefined }); }
  function source(value) {
    onChange({ ...filters, data_mode: value === 'open' ? 'combined' : value, status: value === 'open' ? 'Open' : undefined });
  }
  return <>
    <p className="scope">Tickets created by employees at your level or below.</p>
    <div className="filters panel">
      <label>Data source<select disabled={disabled} value={filters.data_mode === 'combined' && filters.status === 'Open' ? 'open' : filters.data_mode} onChange={e => source(e.target.value)}><option value="open">Live tickets (Open)</option><option value="combined">All tickets (existing + new)</option><option value="live">New tickets only</option><option value="historical_snapshot">Historical snapshot</option></select></label>
      <label>Time range<select disabled={disabled} value={filters.window} onChange={e => filter('window', e.target.value)}><option value="last24h">Last 24 hours</option><option value="last7d">Last 7 days</option><option value="last30d">Last 30 days</option><option value="all">All time</option></select></label>
      <label>Store<select disabled={disabled} value={filters.store_id || ''} onChange={e => filter('store_id', e.target.value)}><option value="">All stores</option>{stores.map(s => <option key={s.store_id} value={s.store_id}>{s.store_id} · {s.store_name}</option>)}</select></label>
      <label>Status<select disabled={disabled} value={filters.status || ''} onChange={e => filter('status', e.target.value)}><option value="">All statuses</option>{['Open', 'In Progress', 'Closed'].map(s => <option key={s}>{s}</option>)}</select></label>
      {onRefresh && <button onClick={onRefresh}>Refresh</button>}
    </div>
    {filters.data_mode === 'historical_snapshot' && <p className="scope">Read-only records up to 10 October 2026, noon IST.</p>}
    {filters.data_mode === 'combined' && <p className="scope">Existing snapshot cases through 10 October 2026, noon IST, plus newly reported tickets. Existing snapshot cases are read-only.</p>}
  </>;
}
