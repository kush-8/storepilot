// Local smoke runner for this generated collection's requests and test scripts.
// This small Postman API shim only implements features used by this collection.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');

async function main() {
  const root = path.resolve(__dirname, '..');
  const collection = JSON.parse(fs.readFileSync(path.join(root, 'postman/StorePilot.postman_collection.json')));
  const environment = JSON.parse(fs.readFileSync(path.join(root, 'postman/StorePilot.local.postman_environment.json')));
  const vars = Object.fromEntries(environment.values.map(v => [v.key, v.value]));
  vars.base_url = process.argv[2] || vars.base_url;
  const replace = text => text.replace(/\{\{([^}]+)\}\}/g, (_, key) => {
    if (key === '$guid') return randomUUID();
    assert.ok(key in vars, `Unknown variable ${key}`);
    return vars[key];
  });
  for (const item of collection.item) {
    const req = item.request;
    const headers = Object.fromEntries(req.header.map(h => [h.key, replace(h.value)]));
    if (req.auth?.type !== 'noauth') headers.Authorization = `Bearer ${vars.access_token}`;
    const response = await fetch(replace(req.url), {
      method: req.method, headers, body: req.body ? replace(req.body.raw) : undefined,
      signal: AbortSignal.timeout(10000),
    });
    const text = await response.text();
    const pm = {
      test: (_name, callback) => callback(),
      response: {
        json: () => JSON.parse(text),
        to: { have: { status: expected => assert.equal(response.status, expected, `${item.name}: ${text}`) } },
      },
      environment: { set: (key, value) => { vars[key] = value; } },
      variables: { replaceIn: replace },
      expect: value => ({ to: {
        eql: expected => assert.deepEqual(value, expected),
        be: { an: expected => { assert.ok(value); assert.equal(typeof value, expected); } },
      } }),
    };
    for (const event of item.event || []) {
      if (event.listen === 'test') vm.runInNewContext(event.script.exec.join('\n'), { pm, encodeURIComponent });
    }
    process.stdout.write(`${item.name}: ${response.status}\n`);
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
