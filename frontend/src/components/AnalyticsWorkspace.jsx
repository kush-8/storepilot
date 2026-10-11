import { useEffect, useRef, useState } from 'react';
import * as api from '../services/api';
import TicketFilters from './TicketFilters';
import { DEFAULT_TICKET_FILTERS } from '../data/ticketFilters';

export default function AnalyticsWorkspace({ stores, onError }) {
  const [filters, setFilters] = useState({ ...DEFAULT_TICKET_FILTERS, status: undefined });
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [asking, setAsking] = useState(false);
  const request = useRef(0);
  useEffect(() => () => { request.current += 1; }, []);

  async function ask(event) {
    event.preventDefault();
    const currentRequest = ++request.current;
    const thread = answer?.result_type === 'clarification' ? answer.analytics_thread_id : null;
    setAsking(true); setAnswer(null);
    try {
      const result = await api.queryAnalytics(question.trim(), filters, thread);
      if (request.current === currentRequest) setAnswer(result);
    } catch (err) {
      if (request.current === currentRequest) onError(err);
    } finally {
      if (request.current === currentRequest) setAsking(false);
    }
  }

  return <>
    <TicketFilters filters={filters} stores={stores} disabled={asking} onChange={next => { setFilters(next); setAnswer(null); }} />
    <section className="panel analytics">
      <h2>Ask StorePilot</h2>
      <p>Ask about tickets, stock, products, vendors, deliveries, returns, or store policies. Selected filters apply to your data questions.</p>
      <form onSubmit={ask}>
        <label>Analytics question<input required maxLength={4000} value={question} onChange={e => setQuestion(e.target.value)} placeholder="What is the most frequent issue in ST004?" /></label>
        <button className="primary" disabled={asking || !question.trim()}>{asking ? 'Asking…' : 'Ask'}</button>
      </form>
      {answer && <div aria-live="polite">
        {answer.rows?.length > 0 && <details><summary>View supporting results</summary><ul className="analytics-results" aria-label="Query results">
          {answer.rows.map((row, i) => <li key={i}>{answer.columns.map((c, index) => <span key={c.key}>
            {index > 0 && ' · '}<strong>{c.label}: </strong>{row[c.key] == null ? '—' : typeof row[c.key] === 'boolean' ? (row[c.key] ? 'Yes' : 'No') : String(row[c.key])}
          </span>)}</li>)}
        </ul></details>}
        {answer.truncated && <p>More results are available. Narrow your question or filters.</p>}
        {answer.citations?.length > 0 && <details><summary>Policy sources</summary>{answer.citations.map(c => <PolicySource key={c.section_id} citation={c} onError={onError} />)}</details>}
        {answer.limitations?.length > 0 && <details><summary>About this answer</summary><ul>{answer.limitations.map((item, i) => <li key={i}>{item}</li>)}</ul></details>}
        <p className="analytics-answer" aria-label="Answer">{answer.answer}</p>
      </div>}
    </section>
  </>;
}

function PolicySource({ citation, onError }) {
  const [section, setSection] = useState(null);
  return <div className="policy"><button onClick={async () => { try { setSection(await api.getPolicy(citation.section_id)); } catch (err) { onError(err); } }}>{citation.heading || citation.section_id}</button>{section && <p>{section.body || section.content || section.text}</p>}</div>;
}
