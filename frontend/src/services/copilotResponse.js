export function fieldLabel(key) {
  const acronyms = new Set(['id', 'sku', 'pos', 'sla', 'sql', 'upi']);
  return key.replace(/([a-z])([A-Z])/g, '$1 $2').split(/[_\s-]+/)
    .map(word => acronyms.has(word.toLowerCase()) ? word.toUpperCase() : word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

// Only consume complete JSON values. Partial or malformed results remain visible.
function readJson(lines, start) {
  const first = lines[start].trim()[0];
  if (first !== '[' && first !== '{') return null;
  let candidate = '';
  for (let end = start; end < lines.length; end += 1) {
    candidate += (end === start ? '' : '\n') + lines[end];
    try {
      const value = JSON.parse(candidate);
      if (value !== null && typeof value === 'object') return { value, end };
    } catch { /* A pretty-printed value may continue on the next line. */ }
  }
  return null;
}

export function parseCopilotResponse(content) {
  const lines = String(content ?? '').replace(/\r\n?/g, '\n').split('\n');
  const blocks = [];
  const append = (type, value) => {
    const previous = blocks.at(-1);
    if (previous?.type === type && ['paragraph', 'ordered', 'unordered'].includes(type)) {
      previous.items.push(value);
    } else blocks.push({ type, items: [value] });
  };
  const appendData = value => {
    const rows = Array.isArray(value) ? value : [value];
    const previous = blocks.at(-1);
    if (previous?.type === 'data') previous.rows.push(...rows);
    else blocks.push({ type: 'data', rows });
  };
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) {
      if (blocks.at(-1)?.type === 'paragraph') blocks.push({ type: 'break' });
      continue;
    }
    if (/^```(?:json)?\s*$/i.test(line)) {
      const closing = lines.findIndex((item, index) => index > i && /^```\s*$/.test(item.trim()));
      if (closing !== -1) {
        try {
          const value = JSON.parse(lines.slice(i + 1, closing).join('\n'));
          if (value !== null && typeof value === 'object') {
            appendData(value); i = closing; continue;
          }
        } catch { /* Keep invalid fenced output as text. */ }
      }
    }
    const json = readJson(lines, i);
    if (json) { appendData(json.value); i = json.end; continue; }
    const source = line.match(/^([\w-]+):\s*(\d+) result row\(s\)\s*(?:\[([^\]]+)\])?\.?$/);
    if (source) {
      blocks.push({ type: 'source', title: fieldLabel(source[1]), count: Number(source[2]), reference: source[3] });
      continue;
    }
    const heading = line.match(/^#{1,6}\s+(.+?)\s*#*$/)
      || line.match(/^(Policy guidance|Operational data|Retail snapshot evidence \(not live availability\)|Recommended steps|Recommendations):$/i);
    if (heading) { blocks.push({ type: 'heading', text: heading[1] }); continue; }
    const ordered = line.match(/^\d+[.)]\s+(.+)$/);
    const unordered = line.match(/^[-*•]\s+(.+)$/);
    if (ordered || unordered) { append(ordered ? 'ordered' : 'unordered', (ordered || unordered)[1]); continue; }
    append('paragraph', lines[i]);
  }
  return blocks.filter(block => block.type !== 'break');
}
