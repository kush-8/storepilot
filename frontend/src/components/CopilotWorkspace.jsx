import { useRef, useState } from 'react';
import * as api from '../services/api';
import CopilotResponse from './CopilotResponse';

export default function CopilotWorkspace({ user, onError, onSaved }) {
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const store = user.assigned_store_id;
  const [sku, setSku] = useState('');
  const [turn, setTurn] = useState(null);
  const [busy, setBusy] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);
  const [notice, setNotice] = useState('');
  const pending = useRef(null);
  const saveKey = useRef(null);
  function handleComposerKeyDown(event) {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    if (!event.repeat) event.currentTarget.form.requestSubmit();
  }
  async function send(event) {
    event.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true); setNotice(''); setTurn(null); setSaveFailed(false);
    try {
      let id = conversation;
      if (!id) { const created = await api.createConversation(store); id = created.conversation_id; setConversation(id); }
      const context = { affected_store_id: store, ...(sku.trim() ? { sku: sku.trim().toUpperCase() } : {}) };
      const signature = JSON.stringify([text.trim(), context]);
      if (pending.current?.signature !== signature) pending.current = { signature, id: api.generateUUID() };
      const result = await api.sendMessage(id, text.trim(), context, pending.current.id);
      const history = await api.getConversation(id);
      setMessages(previous => {
        const responses = new Map(previous.filter(item => item.response).map(item => [item.message_id, item.response]));
        responses.set(result.assistant_message.message_id, result);
        return history.messages.map(item => ({ ...item, response: responses.get(item.message_id) }));
      }); setTurn(result); setText(''); pending.current = null;
      saveKey.current = api.generateUUID();
    } catch (err) { onError(err); } finally { setBusy(false); }
  }
  async function save() {
    setBusy(true);
    try {
      const draft = await api.getDraft(turn.ticket_draft.draft_id);
      // A committed draft is disabled even when the first save reply was lost.
      // Let the backend replay that save with the same key before checking draft eligibility.
      if (!draft.generation_allowed && !saveFailed) throw new Error('This draft expired or was replaced. Send another message to create a new draft.');
      const result = await api.createTicket(draft.draft_id, draft.revision, saveKey.current);
      setNotice(`Ticket created: ${result.ticket.ticket_id}`); setTurn(null); setSaveFailed(false); onSaved();
    } catch (err) { setSaveFailed(true); onError(err); } finally { setBusy(false); }
  }
  return <section className="panel copilot-panel">
    <div className="section-heading"><div><h2>Describe a store issue</h2><p>Get policy guidance, then review and save a ticket.</p></div><button disabled={busy} onClick={() => { setConversation(null); setMessages([]); setTurn(null); setText(''); setNotice(''); pending.current = null; }}>New conversation</button></div>
    <div className="filters"><label>Affected store<input value={store} readOnly /></label><label>SKU (optional)<input value={sku} disabled={busy} onChange={e => setSku(e.target.value)} placeholder="SKU1001" /></label></div>
    <div className="messages" aria-live="polite">{!messages.length && <p className="empty">For example: “Card payments are failing at every register.”</p>}{messages.map((message, index) => <article className={`message ${message.role}`} key={message.message_id || index}><strong>{message.role === 'user' ? 'You' : 'StorePilot'}</strong>{message.role === 'assistant' ? <CopilotResponse content={message.content} response={message.response} /> : <p>{message.content}</p>}</article>)}</div>
    {turn?.recommendations?.length > 0 && <div className="recommendations"><h3>Recommended steps</h3><ol>{turn.recommendations.map((step, index) => <li key={index}>{step}</li>)}</ol></div>}
    {turn?.citations?.length > 0 && <details><summary>Policy sources</summary>{turn.citations.map(c => <PolicySource key={c.section_id} citation={c} onError={onError} />)}</details>}
    {turn?.escalation?.required && <div className="copilot-escalation"><h3>Escalation required</h3><p>{[turn.escalation.team, turn.escalation.sla_minutes != null ? `Response target: ${turn.escalation.sla_minutes} minutes` : null].filter(Boolean).join(' · ') || turn.escalation.reason}</p></div>}
    {turn?.limitations?.length > 0 && <div className="copilot-limitations"><h3>Response limitations</h3><ul>{turn.limitations.map((limit, index) => <li key={index}>{limit}</li>)}</ul></div>}
    {turn?.ticket_draft && <div className="draft"><h3>Review ticket</h3><p>{turn.ticket_draft.title}</p><p>{turn.ticket_draft.priority} · {turn.ticket_draft.category} · {turn.ticket_draft.affected_store_id}</p>{turn.ticket_draft.approval_required && <p>Human approval required.</p>}<p>Saving records the issue. Follow the recommended steps with your team.</p><button className="primary" disabled={busy} onClick={save}>{busy ? 'Saving…' : saveFailed ? 'Retry ticket save' : 'Generate ticket'}</button></div>}
    {notice && <p className="success" role="status">{notice}</p>}
    <form onSubmit={send}><label>Message<textarea value={text} maxLength={4000} required disabled={busy} onChange={e => setText(e.target.value)} onKeyDown={handleComposerKeyDown} aria-describedby="copilot-composer-help" placeholder="What happened?" /></label><div className="composer-footer"><span id="copilot-composer-help">Enter to send · Shift+Enter for a new line. Local policy guidance. Review recommendations before acting.</span><button className="primary" disabled={busy || !text.trim()}>{busy ? 'Working…' : 'Send'}</button></div></form>
  </section>;
}

function PolicySource({ citation, onError }) {
  const [section, setSection] = useState(null);
  return <div className="policy"><button onClick={async () => { try { setSection(await api.getPolicy(citation.section_id)); } catch (err) { onError(err); } }}>{citation.heading || citation.section_id}</button>{section && <p>{section.body || section.content || section.text}</p>}</div>;
}

