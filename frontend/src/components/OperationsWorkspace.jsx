import { useEffect, useState } from 'react';
import * as api from '../services/api';
import TicketFilters from './TicketFilters';
import { DEFAULT_TICKET_FILTERS } from '../data/ticketFilters';

export default function OperationsWorkspace({ user, stores, revision, onError, onCopilot }) {
  const [filters, setFilters] = useState(DEFAULT_TICKET_FILTERS);
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(true);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [selected, setSelected] = useState(null);
  useEffect(() => {
    let active = true;
    // Clear the previous result when a new request starts.
    // eslint-disable-next-line react/set-state-in-effect
    setBusy(true); setData(null);
    Promise.all([api.getDashboard(filters), api.getTickets({ ...filters, limit: 20, offset })])
      .then(([dashboard, tickets]) => { if (active) setData({ dashboard, tickets }); })
      .catch(err => { if (active) onError(err); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [filters, offset, revision, refresh, onError]);
  return <>
    <TicketFilters filters={filters} stores={stores} onChange={next => { setOffset(0); setFilters(next); }} onRefresh={() => setRefresh(value => value + 1)} />
    {busy && <p role="status">Loading tickets…</p>}
    {!busy && !data && <p className="empty">Could not load data. Use Refresh to retry.</p>}
    {data && <>
      <div className="metrics">{[['Unresolved', 'unresolved'], ['Critical P1', 'p1_unresolved'], ['In progress', 'in_progress'], ['Closed', 'closed']].map(([label, key]) => <div className="panel metric" key={key}><span>{label}</span><strong>{data.dashboard.metrics[key]}</strong></div>)}</div>
      <section className="panel"><div className="section-heading"><h2>Recent tickets</h2><button className="primary" onClick={onCopilot}>Report an issue</button></div>
        {!data.tickets.items.length ? <p className="empty">No tickets match these filters.</p> : <div className="table-scroll"><table><thead><tr><th>Ticket</th><th>Issue</th><th>Store</th><th>Priority</th><th>Status</th></tr></thead><tbody>{data.tickets.items.map(t => <tr key={t.ticket_id}><td><button className="text-button" onClick={async () => { try { setSelected(await api.getTicket(t.ticket_id)); } catch (err) { onError(err); } }}>{t.ticket_id}</button></td><td>{t.title}</td><td>{t.affected_store_id}</td><td><span className={`priority ${t.priority}`}>{t.priority}</span></td><td>{t.status}</td></tr>)}</tbody></table></div>}
        <div className="pagination"><span>{data.tickets.total} tickets</span><button disabled={!offset || busy} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous</button><button disabled={offset + 20 >= data.tickets.total || busy} onClick={() => setOffset(value => value + 20)}>Next</button></div>
      </section>
    </>}
    {selected && <TicketDetail key={selected.ticket_id} ticket={selected} user={user} onClose={() => setSelected(null)} onError={onError} onUpdated={ticket => { setSelected(ticket); setRefresh(value => value + 1); }} />}
  </>;
}

function TicketDetail({ ticket, user, onClose, onError, onUpdated }) {
  const [status, setStatus] = useState(ticket.status);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const editable = ticket.origin !== 'historical_import' && ticket.created_by_employee_id === user.employee_id;
  async function update(event) {
    event.preventDefault(); setBusy(true);
    try { onUpdated(await api.updateTicketStatus(ticket.ticket_id, status, ticket.version, reason.trim() || null)); }
    catch (err) { onError(err); if (err.status === 409) { try { const latest = await api.getTicket(ticket.ticket_id); setStatus(latest.status); onUpdated(latest); } catch (next) { onError(next); } } }
    finally { setBusy(false); }
  }
  return <div className="modal-backdrop"><section className="panel modal" role="dialog" aria-modal="true" aria-labelledby="ticket-title"><button className="close" onClick={onClose} autoFocus>Close</button><h2 id="ticket-title">{ticket.ticket_id}</h2><h3>{ticket.title}</h3><p>{ticket.description}</p><p>{ticket.priority} · {ticket.status} · {ticket.affected_store_id}</p>{ticket.recommendations?.length > 0 && <ol>{ticket.recommendations.map((step, i) => <li key={i}>{step}</li>)}</ol>}{ticket.approval_required && <p>Approval: {ticket.approval_status}</p>}{editable ? <form onSubmit={update}><label>Status<select value={status} onChange={e => setStatus(e.target.value)}>{(ticket.status === 'Closed' ? ['Closed', 'Open'] : ['Open', 'In Progress', 'Closed']).map(s => <option key={s}>{s}</option>)}</select></label><label>Reason{ticket.status === 'Closed' ? ' (required to reopen)' : ' (optional)'}<input required={ticket.status === 'Closed'} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label><button className="primary" disabled={busy || status === ticket.status}>{busy ? 'Updating…' : 'Update status'}</button></form> : <p className="scope">Read-only. Only creators can update live tickets.</p>}</section></div>;
}
