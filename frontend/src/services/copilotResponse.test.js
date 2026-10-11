import assert from 'node:assert/strict';
import test from 'node:test';
import { fieldLabel, parseCopilotResponse } from './copilotResponse.js';

test('groups query rows and keeps policy, sources, and preview limits separate', () => {
  const blocks = parseCopilotResponse(`Policy guidance:
1. Check stock.
2. Contact the supervisor.

Operational data:
Retail snapshot evidence (not live availability):
inventory: 10 result row(s) [retail:generated-sql:inventory].
{"sku":"SKU1001","on_hand":0}
{"sku":"SKU1002","on_hand":5,"reserved":null}
Preview only; inspect structured evidence for details and limits.
pricing: 1 result row(s) [retail:generated-sql:pricing].
{"price":99.5}`);
  assert.deepEqual(blocks.filter(block => block.type === 'data').map(block => block.rows.length), [2, 1]);
  assert.equal(blocks.find(block => block.type === 'source').count, 10);
  assert.equal(blocks.find(block => block.type === 'ordered').items.length, 2);
  assert.ok(blocks.some(block => block.items?.[0].startsWith('Preview only')));
});

test('parses pretty-printed and fenced JSON including nested data', () => {
  const content = '```json\n[\n {"sku":"SKU1001","details":{"note":"braces } inside text"},"active":false}\n]\n```';
  const blocks = parseCopilotResponse(content);
  assert.equal(blocks.length, 1);
  assert.equal(blocks[0].rows[0].details.note, 'braces } inside text');
  assert.equal(blocks[0].rows[0].active, false);
  assert.deepEqual(parseCopilotResponse('[]')[0].rows, []);
});

test('preserves malformed and truncated JSON and plain response paragraphs', () => {
  const content = 'No matching records.\n\n{"sku":"SKU1001", "on_hand":\nPlease retry.';
  const blocks = parseCopilotResponse(content);
  assert.equal(blocks.length, 2);
  assert.equal(blocks[1].items.join('\n'), '{"sku":"SKU1001", "on_hand":\nPlease retry.');
  assert.equal(blocks.some(block => block.type === 'data'), false);
});

test('makes database field names readable without changing their values', () => {
  assert.equal(fieldLabel('store_id'), 'Store ID');
  assert.equal(fieldLabel('sku'), 'SKU');
  assert.equal(fieldLabel('on_hand'), 'On Hand');
  assert.equal(fieldLabel('salePrice'), 'Sale Price');
});
