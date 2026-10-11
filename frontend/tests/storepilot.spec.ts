import { test, expect, login, navigate, prepareDraft } from './api-fixture'
import type { Page } from '@playwright/test'

async function mockQueryResponses(page: Page, contents: string[]) {
  const messages: { message_id: string; role: string; content: string }[] = []
  let turn = 0
  await page.route('**/api/conversations/*', async route => {
    await route.fulfill({ json: { messages } })
  })
  await page.route('**/api/conversations/*/messages', async route => {
    const assistant = { message_id: `assistant-${turn}`, role: 'assistant', content: contents[turn++] }
    messages.push({ message_id: `user-${turn}`, role: 'user', content: route.request().postDataJSON().content }, assistant)
    await route.fulfill({ json: {
      assistant_message: assistant, category: 'Inventory and Replenishment', priority: 'P2',
      result_type: 'recommendation', recommendations: [], citations: [], evidence: [],
      ticket_draft: null, limitations: ['Snapshot data; check current stock before acting.'],
    } })
  })
}

test('StorePilot has Dashboard, Copilot and a separate Analytics/Query tab', async ({ page, api }) => {
  await login(page)
  await expect(page.getByText('StorePilot', { exact: true }).first()).toBeVisible()
  await expect(page.getByText(/your level or below/i)).toBeVisible()
  await expect(page.getByLabel('Data source')).toHaveValue('open')
  await expect(page.getByLabel('Time range')).toHaveValue('all')
  await expect(page.getByRole('combobox', { name: 'Status', exact: true })).toHaveValue('Open')
  const navigation = page.getByRole('navigation', { name: 'Main navigation' })
  await expect(navigation.getByRole('button')).toHaveCount(3)
  for (const name of ['Dashboard', 'Copilot', 'Analytics/Query']) {
    await expect(navigation.getByRole('button', { name, exact: true })).toBeVisible()
  }
  for (const name of ['Overview', 'Tickets', 'Evaluation']) {
    await expect(page.getByRole('link', { name, exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name, exact: true })).toHaveCount(0)
  }
  await expect(page.getByLabel('Analytics question')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Recent tickets', exact: true })).toBeVisible()
  await navigate(page, 'Analytics/Query')
  await expect(page.getByRole('heading', { name: 'Analytics/Query', exact: true })).toBeVisible()
  await expect(page.getByLabel('Analytics question')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Recent tickets', exact: true })).toHaveCount(0)
  expect(api.tokensMissing).toEqual([])
})

test('follow-up, recommendation and ticket save update Dashboard', async ({ page, api }) => {
  await login(page)
  await prepareDraft(page)
  await expect(page.getByText(/Escalate to Store Manager and POS Support/i).first()).toBeVisible()
  await page.getByRole('button', { name: 'Generate ticket', exact: true }).click()
  await expect(page.getByText(/Ticket created.*SP-TEST-001/i)).toBeVisible()
  expect(api.saves).toBe(1)
  await navigate(page, 'Dashboard')
  await expect(page.getByRole('row').filter({ hasText: 'SP-TEST-001' })).toBeVisible()
  expect(api.tokensMissing).toEqual([])
})

test('failed save preserves draft and retries with the same idempotency key', async ({ page, api }) => {
  await login(page)
  await prepareDraft(page)
  api.failNextSave = true
  await page.getByRole('button', { name: 'Generate ticket', exact: true }).click()
  await expect(page.getByText(/Ticket created/i)).toHaveCount(0)
  await page.getByRole('button', { name: /Retry/i }).click()
  await expect(page.getByText(/Ticket created.*SP-TEST-001/i)).toBeVisible()
  expect(api.saves).toBe(2)
  expect(api.keys[0]).not.toBe('')
  expect(api.keys[0]).toBe(api.keys[1])
})

test('Analytics/Query uses selected filters without generating an incident ticket', async ({ page, api }) => {
  await login(page)
  await navigate(page, 'Analytics/Query')
  await page.getByLabel('Data source').selectOption('live')
  await page.getByLabel('Time range').selectOption('last7d')
  await page.getByRole('combobox', { name: 'Store', exact: true }).selectOption('ST003')
  await page.getByRole('textbox', { name: /Analytics question|Ask StorePilot/i })
    .fill('Count visible unresolved tickets by store.')
  const query = page.waitForRequest(request => request.url().endsWith('/api/dashboard/analytics'))
  await page.getByRole('button', { name: /^(Ask|Ask StorePilot)$/i }).click()
  expect((await query).postDataJSON().filters).toEqual({ data_mode: 'live', window: 'last7d', store_id: 'ST003' })
  await expect(page.getByText('There is one visible unresolved outage ticket.')).toBeVisible()
  await expect(page.getByRole('list', { name: 'Query results' }).getByRole('listitem').filter({ hasText: 'ST003' })).toContainText('1')
  await page.getByLabel('Time range').selectOption('all')
  await expect(page.getByText('There is one visible unresolved outage ticket.')).toHaveCount(0)
  expect(api.saves).toBe(0)
  expect(api.tokensMissing).toEqual([])
})

test('logout clears private conversation and bearer token from browser storage', async ({ page }) => {
  await login(page)
  await prepareDraft(page)
  await page.getByRole('button', { name: /^(Log out|Sign out)$/i }).click()
  await expect(page.getByLabel('Employee ID', { exact: true })).toBeVisible()
  await expect(page.getByText('All registers at ST001 cannot take card payments.')).toHaveCount(0)
  const saved = await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))
  expect(saved).not.toContain('fixture-opaque-bearer-token')
})

test('login and chat controls remain usable at mobile width', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  await login(page)
  await navigate(page, 'Analytics/Query')
  await expect(page.getByLabel('Analytics question')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360)
  await navigate(page, 'Copilot')
  const composer = page.getByRole('textbox', { name: 'Message', exact: true })
  await expect(composer).toBeVisible()
  await composer.focus()
  await expect(composer).toBeFocused()
  await composer.fill('Card reader stopped working.')
  await composer.press('Shift+Enter')
  await composer.press('A')
  await expect(composer).toHaveValue('Card reader stopped working.\nA')
  await expect(page.locator('.message.user')).toHaveCount(0)
  await composer.press('Enter')
  await expect(page.getByText(/one register affected.*all registers/i)).toBeVisible()
  await expect(composer).toHaveValue('')
  await expect(page.locator('.message.user')).toHaveCount(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360)
})

test('Copilot starts with category and priority, then renders database rows and policy steps', async ({ page }) => {
  await login(page)
  await navigate(page, 'Copilot')
  await mockQueryResponses(page, [`Policy guidance:
1. **Check stock** with the supervisor.
2. Follow the replenishment policy.

Operational data:
Retail snapshot evidence (not live availability):
inventory: 7 result row(s) [retail:generated-sql:inventory].
{"store_id":"ST001","sku":"SKU1001","on_hand":0}
{"store_id":"ST001","sku":"SKU1002","on_hand":5,"reserved":null}
Preview only; inspect structured evidence for details and limits.`, 'Follow up with your supervisor.'])
  const composer = page.getByRole('textbox', { name: 'Message', exact: true })
  await composer.fill('Show stock levels.')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  const response = page.locator('.message.assistant').first()
  await expect(response.getByLabel('Issue classification')).toContainText('Inventory and Replenishment')
  await expect(response.getByLabel('Issue classification')).toContainText('Priority levelP2')
  expect(await response.locator('.copilot-response').evaluate(element => element.firstElementChild?.getAttribute('aria-label'))).toBe('Issue classification')
  await expect(response.getByRole('columnheader', { name: 'On Hand' })).toBeVisible()
  await expect(response.getByRole('columnheader', { name: 'SKU', exact: true })).toBeVisible()
  await expect(response.getByRole('row').filter({ hasText: 'SKU1001' })).toContainText('0')
  await expect(response.getByRole('row').filter({ hasText: 'SKU1002' })).toContainText('—')
  await expect(response.getByText('7 result rows', { exact: true })).toBeVisible()
  await expect(response.getByText('2 records shown', { exact: true })).toBeVisible()
  await expect(response.getByText(/Preview only/)).toBeVisible()
  await expect(response.getByRole('listitem')).toHaveCount(2)
  await expect(response).not.toContainText('"on_hand"')
  await expect(page.getByRole('heading', { name: 'Response limitations' })).toBeVisible()
  await composer.fill('What next?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.locator('.message.assistant')).toHaveCount(2)
  await expect(response.getByLabel('Issue classification')).toContainText('P2')
})

test('Copilot safely renders fenced, nested, empty and malformed query results on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  await login(page)
  await navigate(page, 'Copilot')
  await mockQueryResponses(page, ['```json\n[{"sku":"SKU1001","details":{"note":"<img src=x onerror=alert(1)>"},"active":false}]\n```\n\nreturns: 0 result row(s) [retail:generated-sql:returns].\n[]\n\n{"sku":"truncated"'])
  await page.getByRole('textbox', { name: 'Message', exact: true }).fill('Show records.')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  const response = page.locator('.message.assistant')
  await expect(response.getByRole('cell', { name: 'No', exact: true })).toBeVisible()
  await expect(response.getByText('<img src=x onerror=alert(1)>', { exact: true })).toBeVisible()
  await expect(response.locator('img')).toHaveCount(0)
  await expect(response.getByText('No matching records.', { exact: true })).toBeVisible()
  await expect(response.getByText('{"sku":"truncated"', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360)
})
