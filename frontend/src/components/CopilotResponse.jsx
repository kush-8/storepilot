import { fieldLabel, parseCopilotResponse } from '../services/copilotResponse';

function InlineText({ text }) {
  return String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`')) return <code key={index}>{part.slice(1, -1)}</code>;
    return part;
  });
}

function DataValue({ value, depth = 0 }) {
  if (value === null || value === undefined) return <span className="data-missing">—</span>;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value !== 'object') return String(value);
  // Bound rendering for unusually deep JSON without losing the original value.
  if (depth >= 6) return <code>{JSON.stringify(value)}</code>;
  if (Array.isArray(value)) return <DataRows rows={value} depth={depth + 1} />;
  return <dl className="data-fields">{Object.entries(value).map(([key, item]) => <div key={key}>
    <dt>{fieldLabel(key)}</dt><dd><DataValue value={item} depth={depth + 1} /></dd>
  </div>)}</dl>;
}

function DataRows({ rows, depth = 0 }) {
  if (!rows.length) return <p className="empty">No matching records.</p>;
  if (!rows.every(row => row !== null && typeof row === 'object' && !Array.isArray(row))) {
    return <ul>{rows.map((value, index) => <li key={index}><DataValue value={value} depth={depth} /></li>)}</ul>;
  }
  const columns = [...new Set(rows.flatMap(row => Object.keys(row)))];
  if (!columns.length) return <p className="empty">No fields returned.</p>;
  return <div className="table-scroll copilot-data-scroll" role="region" aria-label="Database query results" tabIndex={0}>
    <table className="copilot-data-table"><caption>{rows.length} {rows.length === 1 ? 'record shown' : 'records shown'}</caption>
      <thead><tr>{columns.map(key => <th key={key} scope="col">{fieldLabel(key)}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>{columns.map(key => <td key={key}><DataValue value={row[key]} depth={depth} /></td>)}</tr>)}</tbody>
    </table>
  </div>;
}

export default function CopilotResponse({ content, response }) {
  return <div className="copilot-response">
    {(response?.category || response?.priority) && <div className="copilot-response-meta" aria-label="Issue classification">
      <div><span>Category</span><strong>{response.category || 'Not assigned'}</strong></div>
      <div><span>Priority level</span>{response.priority
        ? <strong className={`priority ${response.priority}`}>{response.priority}</strong>
        : <strong>{response.result_type === 'clarification' ? 'Awaiting clarification' : 'Not assigned'}</strong>}</div>
    </div>}
    {parseCopilotResponse(content).map((block, index) => {
      if (block.type === 'heading') return <h3 key={index}>{block.text}</h3>;
      if (block.type === 'source') return <div className="copilot-data-source" key={index}>
        <h4>{block.title}</h4><span>{block.count} {block.count === 1 ? 'result row' : 'result rows'}</span>
        {block.reference && <small>Source: {block.reference}</small>}
      </div>;
      if (block.type === 'data') return <DataRows key={index} rows={block.rows} />;
      if (block.type === 'ordered' || block.type === 'unordered') {
        const List = block.type === 'ordered' ? 'ol' : 'ul';
        return <List key={index}>{block.items.map((item, i) => <li key={i}><InlineText text={item} /></li>)}</List>;
      }
      return <p key={index}><InlineText text={block.items.join('\n')} /></p>;
    })}
  </div>;
}
