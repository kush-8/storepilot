import { randomUUID } from 'node:crypto'
import { test as base, expect, type Page } from '@playwright/test'

type State = {
  failNextSave: boolean
  saves: number
  keys: string[]
  tokensMissing: string[]
  created: boolean
}

export const test = base.extend<{ api: State }>({
  api: [async ({ page }, use) => {
    const state: State = {
      failNextSave: false, saves: 0, keys: [], tokensMissing: [], created: false,
    }
    let messages: Record<string, unknown>[] = []
    let turns = 0
    const conversationId = randomUUID()
    const draftId = randomUUID()
    const now = new Date().toISOString()
    const context = {
      scope: {
        viewer_employee_id: 'E9001', viewer_current_level: 1,
        rule: 'creator_current_level <= viewer_current_level',
      },
      filters: { data_mode: 'combined', window: 'all', status: 'Open' },
      time_window: { start: null, end: now, interval: '(start,end]', timezone: 'Asia/Kolkata' },
      source_versions: { retail: 'fixture-source', application: 'fixture-version' },
    }
    const employee = {
      employee_id: 'E9001', assigned_store_id: 'ST001', role: 'Cashier', escalation_level: 1,
    }
    const citation = {
      section_id: '02_pos_pricing_returns_policy.md#pos-card-reader-runbook',
      filename: '02_pos_pricing_returns_policy.md', heading: 'POS Card Reader Runbook',
      source_hash: 'fixture-policy-hash',
    }
    const escalation = {
      required: true, team: 'Store Manager + POS Support', channel: 'pos_p1_queue',
      sla_minutes: 15, reason: 'All registers cannot take card payments.',
      human_approval_required: true,
    }
    const steps = ['Escalate to Store Manager and POS Support.',
      'Use approved alternate tender options if permitted.']
    const draft = {
      draft_id: draftId, conversation_id: conversationId, revision: 1,
      title: 'Store-wide card payment outage', description: 'All registers at ST001 fail.',
      affected_store_id: 'ST001', sku: null, register_id: null,
      category: 'POS and Payments', priority: 'P1', confidence: 0.9,
      recommendations: steps, citations: [citation], evidence: [], escalation,
      review_required: true, approval_required: true, validation_status: 'validated',
      generation_allowed: true, expires_at: new Date(Date.now() + 1_800_000).toISOString(),
    }
    const ticket = {
      ticket_id: 'SP-TEST-001', title: draft.title, description: draft.description,
      created_by_employee_id: 'E9001', creator_current_level: 1, affected_store_id: 'ST001',
      sku: null, register_id: null, category: 'POS and Payments', priority: 'P1',
      status: 'Open', confidence: 0.9, review_required: true, approval_required: true,
      approval_status: 'pending', origin: 'copilot', priority_provenance: 'policy_validated',
      policy_validation_status: 'validated', created_at: now, updated_at: now, closed_at: null,
      version: 1, recommendations: steps, citations: [citation], evidence: [], escalation,
      events: [{ event_id: randomUUID(), event_type: 'created', actor_employee_id: 'E9001',
        old_status: null, new_status: 'Open', note: null, created_at: now }],
    }
    await page.route('**/api/**', async route => {
      const request = route.request()
      const path = new URL(request.url()).pathname
      const method = request.method()
      const body = request.postDataJSON() ?? {}
      const send = (status: number, data: unknown) => route.fulfill({
        status, contentType: 'application/json', body: JSON.stringify(data),
      })
      const error = (status: number, code: string) => send(status, {
        code, message: code === 'not_found' ? 'Resource not found.' : 'Please retry.',
        request_id: randomUUID(),
      })
      if (path === '/api/health') return send(200, {
        status: 'ok', capabilities: {
          source_database: 'ready', application_database: 'ready',
          chat: 'ready', retrieval: 'ready',
        },
      })
      if (path === '/api/auth/login') {
        if (body.employee_id !== 'E9001' || body.store_id !== 'ST001')
          return error(401, 'invalid_login')
        return send(200, {
          access_token: 'fixture-opaque-bearer-token', token_type: 'Bearer', expires_in: 1800,
          expires_at: new Date(Date.now() + 1_800_000).toISOString(), employee,
        })
      }
      if (request.headers().authorization !== 'Bearer fixture-opaque-bearer-token') {
        state.tokensMissing.push(path)
        return error(401, 'unauthorized')
      }
      if (path === '/api/auth/logout') return route.fulfill({ status: 204 })
      if (path === '/api/me') return send(200, employee)
      if (path === '/api/stores') return send(200, { items: [
        { store_id: 'ST001', store_name: 'Test store one', city: 'Jalandhar',
          region: 'Punjab', location_type: 'store' },
        { store_id: 'ST003', store_name: 'Test store three', city: 'Amritsar',
          region: 'Punjab', location_type: 'store' },
      ] })
      if (path === '/api/dashboard') return send(200, {
        context, data_revision: state.created ? 'saved' : 'empty',
        metrics: { total: state.created ? 1 : 0, open: state.created ? 1 : 0, in_progress: 0,
          closed: 0, unresolved: state.created ? 1 : 0,
          p1_unresolved: state.created ? 1 : 0, p2_unresolved: 0 },
        by_priority: [], by_category: [], by_store: [],
      })
      if (path === '/api/conversations' && method === 'POST') return send(201, {
        conversation_id: conversationId, owner_employee_id: 'E9001',
        affected_store_id: body.affected_store_id ?? 'ST001',
        created_at: now, updated_at: now, messages,
      })
      if (path.endsWith('/messages') && method === 'POST') {
        turns += 1
        const content = String(body.content ?? '')
          .replace(/9876543210/g, '[phone masked]')
          .replace(/4111\s*1111\s*1111\s*1111/g, '[card redacted]')
        messages.push({ message_id: randomUUID(), role: 'user', content,
          created_at: now, pii_checked: true })
        const question = turns === 1 ? 'Is one register affected, or are all registers unable to take cards?' : null
        const assistant = { message_id: randomUUID(), role: 'assistant',
          content: question ?? 'Escalate this store-wide payment outage immediately.',
          created_at: now, pii_checked: true }
        messages.push(assistant)
        return send(200, {
          request_id: randomUUID(), conversation_id: conversationId, assistant_message: assistant,
          result_type: question ? 'clarification' : 'recommendation',
          route: question ? 'Clarify' : 'RAG', follow_up_question: question,
          category: 'POS and Payments', priority: question ? null : 'P1',
          recommendations: question ? [] : steps, citations: question ? [] : [citation],
          evidence: [], escalation: question ? null : escalation,
          guardrails: { pii_checked: true, pii_detected: content !== body.content,
            safety_refusal: false, human_review_required: !question },
          ticket_draft: question ? null : draft, limitations: [],
        })
      }
      if (path.startsWith('/api/conversations/')) return send(200, {
        conversation_id: conversationId, owner_employee_id: 'E9001', affected_store_id: 'ST001',
        created_at: now, updated_at: now, messages,
      })
      if (path.startsWith('/api/ticket-drafts/')) return send(200, draft)
      if (path === '/api/tickets' && method === 'POST') {
        state.saves += 1
        state.keys.push(request.headers()['idempotency-key'] ?? '')
        if (state.failNextSave) {
          state.failNextSave = false
          return error(503, 'save_unavailable')
        }
        state.created = true
        return send(201, { ticket, idempotent_replay: false })
      }
      if (path === '/api/tickets') return send(200, {
        items: state.created ? [ticket] : [], total: state.created ? 1 : 0,
        limit: 50, offset: 0, context,
      })
      if (path === '/api/tickets/SP-TEST-001') return send(200, ticket)
      if (path === '/api/dashboard/analytics') return send(200, {
        request_id: randomUUID(), analytics_thread_id: randomUUID(), result_type: 'answer',
        answer: 'There is one visible unresolved outage ticket.',
        follow_up_question: null, intent: 'ticket_counts', context,
        columns: [{ key: 'store_id', label: 'Store', value_type: 'string' },
          { key: 'ticket_count', label: 'Tickets', value_type: 'number' }],
        rows: [{ store_id: 'ST003', ticket_count: 1 }], total_rows: 1, truncated: false,
        query_template_ids: ['ticket_counts'], citations: [], evidence: [],
        guardrails: { pii_checked: true, pii_detected: false,
          safety_refusal: false, human_review_required: false }, limitations: [],
      })
      return error(404, 'not_found')
    })
    await use(state)
  }, { auto: true }],
})

export { expect }

export async function login(page: Page) {
  await page.goto('/')
  await page.getByLabel('Employee ID', { exact: true }).fill('E9001')
  await page.getByLabel('Store ID', { exact: true }).fill('ST001')
  await page.getByRole('button', { name: /^(Log in|Sign in)$/i }).click()
  await expect(page.getByRole('heading', { name: 'Dashboard', exact: true })).toBeVisible()
}

export async function navigate(page: Page, name: string) {
  await page.getByRole('link', { name, exact: true })
    .or(page.getByRole('button', { name, exact: true })).first().click()
}

export async function prepareDraft(page: Page) {
  await navigate(page, 'Copilot')
  await page.getByRole('textbox', { name: 'Message', exact: true }).fill('Card reader stopped working.')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText(/one register affected.*all registers/i)).toBeVisible()
  await page.getByRole('textbox', { name: 'Message', exact: true })
    .fill('All registers at ST001 cannot take card payments.')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Generate ticket', exact: true })).toBeVisible()
}
