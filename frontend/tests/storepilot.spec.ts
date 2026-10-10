import { test, expect, login, navigate, prepareDraft } from './api-fixture'

test('StorePilot has Dashboard and Copilot, with analytics inside Dashboard', async ({ page, api }) => {
  await login(page)
  await expect(page.getByText('StorePilot', { exact: true }).first()).toBeVisible()
  await expect(page.getByText(/your level or below/i)).toBeVisible()
  for (const name of ['Overview', 'Analytics', 'Evaluation']) {
    await expect(page.getByRole('link', { name, exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name, exact: true })).toHaveCount(0)
  }
  await expect(page.getByRole('textbox', { name: /Analytics question|Ask StorePilot/i })).toBeVisible()
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

test('dashboard Analytics answers without generating an incident ticket', async ({ page, api }) => {
  await login(page)
  await page.getByRole('textbox', { name: /Analytics question|Ask StorePilot/i })
    .fill('Count visible unresolved tickets by store.')
  await page.getByRole('button', { name: /^(Ask|Ask StorePilot)$/i }).click()
  await expect(page.getByText('There is one visible unresolved outage ticket.')).toBeVisible()
  expect(api.saves).toBe(0)
  expect(api.tokensMissing).toEqual([])
})

test('logout clears private conversation and bearer token from browser storage', async ({ page }) => {
  await login(page)
  await prepareDraft(page)
  await page.getByRole('button', { name: /^(Log out|Sign out)$/i }).click()
  await expect(page.getByLabel('Employee ID', { exact: true })).toBeVisible()
  await expect(page.getByText('All registers at ST003 cannot take card payments.')).toHaveCount(0)
  const saved = await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))
  expect(saved).not.toContain('fixture-opaque-bearer-token')
})

test('login and chat controls remain usable at mobile width', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  await login(page)
  await navigate(page, 'Copilot')
  const composer = page.getByRole('textbox', { name: 'Message', exact: true })
  await expect(composer).toBeVisible()
  await composer.focus()
  await expect(composer).toBeFocused()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360)
})
