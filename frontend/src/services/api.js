// StorePilot API Client
// Implements all 16 operations from openapi.json for the FastAPI backend

const API_BASE = '/api';
const TOKEN_KEY = 'psm_access_token';

/**
 * Get current stored bearer token
 */
export function getAuthToken() {
  try {
    return (
      localStorage.getItem(TOKEN_KEY) ||
      sessionStorage.getItem(TOKEN_KEY) ||
      null
    );
  } catch {
    return null;
  }
}

/**
 * Set bearer token in storage
 */
export function setAuthToken(token, remember = true) {
  try {
    if (remember) {
      localStorage.setItem(TOKEN_KEY, token);
      sessionStorage.removeItem(TOKEN_KEY);
    } else {
      sessionStorage.setItem(TOKEN_KEY, token);
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // Ignore storage errors
  }
}

/**
 * Clear stored token
 */
export function clearAuthToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Ignore storage errors
  }
}

/**
 * Generate a random UUID v4
 */
export function generateUUID() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Core HTTP Request Wrapper
 */
async function apiRequest(endpoint, options = {}) {
  const token = getAuthToken();
  const headers = {
    'Accept': 'application/json',
    ...(options.headers || {}),
  };

  if (options.body && !(options.body instanceof FormData) && typeof options.body === 'object') {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }

  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const url = `${API_BASE}${endpoint}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (response.status === 204) {
      return null;
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const error = new Error(data.message || data.detail || `Request failed with status ${response.status}`);
      error.status = response.status;
      error.code = data.code || 'error';
      error.requestId = data.request_id || response.headers.get('X-Request-ID');
      error.details = data;
      throw error;
    }

    return data;
  } catch (err) {
    // If network error (backend not running)
    if (!err.status) {
      err.isNetworkError = true;
      err.message = 'Unable to reach StorePilot API server (127.0.0.1:8000). Ensure backend is running.';
    }
    throw err;
  }
}

// =============================================================================
// 1. HEALTH & SYSTEM CAPABILITIES
// =============================================================================

/**
 * GET /api/health
 */
export async function getHealth() {
  return apiRequest('/health');
}

// =============================================================================
// 2. AUTHENTICATION & SESSION
// =============================================================================

/**
 * POST /api/auth/login
 * @param {string} employeeId - e.g. "E0007", "E0035", "E0001"
 * @param {string} storeId - e.g. "ST001", "ST008"
 * @param {boolean} remember - persist token across restarts
 */
export async function login(employeeId, storeId, remember = true) {
  const data = await apiRequest('/auth/login', {
    method: 'POST',
    body: {
      employee_id: employeeId,
      store_id: storeId,
    },
  });

  if (data?.access_token) {
    setAuthToken(data.access_token, remember);
  }
  return data;
}

/**
 * POST /api/auth/logout
 */
export async function logout() {
  try {
    await apiRequest('/auth/logout', { method: 'POST' });
  } finally {
    clearAuthToken();
  }
}

/**
 * GET /api/me
 */
export async function getMe() {
  return apiRequest('/me');
}

// =============================================================================
// 3. STORES DIRECTORY
// =============================================================================

/**
 * GET /api/stores
 */
export async function getStores() {
  return apiRequest('/stores');
}

// =============================================================================
// 4. CONVERSATIONS & COPILOT CHAT
// =============================================================================

/**
 * POST /api/conversations
 * @param {string} affectedStoreId - optional store ID
 */
export async function createConversation(affectedStoreId = null) {
  const body = {};
  if (affectedStoreId) {
    body.affected_store_id = affectedStoreId;
  }
  return apiRequest('/conversations', {
    method: 'POST',
    body,
  });
}

/**
 * GET /api/conversations/{conversation_id}
 */
export async function getConversation(conversationId) {
  return apiRequest(`/conversations/${conversationId}`);
}

/**
 * POST /api/conversations/{conversation_id}/messages
 * @param {string} conversationId
 * @param {string} content
 * @param {object} context - { affected_store_id, sku, register_id }
 * @param {string} clientMessageId - optional UUID
 */
export async function sendMessage(conversationId, content, context = {}, clientMessageId = null) {
  return apiRequest(`/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: {
      content,
      client_message_id: clientMessageId || generateUUID(),
      context: context || {},
    },
  });
}

// =============================================================================
// 5. TICKET DRAFTS & CREATION
// =============================================================================

/**
 * GET /api/ticket-drafts/{draft_id}
 */
export async function getDraft(draftId) {
  return apiRequest(`/ticket-drafts/${draftId}`);
}

/**
 * POST /api/tickets
 * @param {string} draftId
 * @param {number} draftRevision
 * @param {string} idempotencyKey
 */
export async function createTicket(draftId, draftRevision, idempotencyKey = null) {
  const key = idempotencyKey || `save-${generateUUID()}`;
  return apiRequest('/tickets', {
    method: 'POST',
    headers: {
      'Idempotency-Key': key,
    },
    body: {
      draft_id: draftId,
      draft_revision: draftRevision,
    },
  });
}

// =============================================================================
// 6. TICKETS LISTING & DETAILS
// =============================================================================

/**
 * GET /api/tickets
 * @param {object} params - { data_mode, window, store_id, sku, status, priority, category, search, limit, offset }
 */
export async function getTickets(params = {}) {
  const query = new URLSearchParams();

  if (params.data_mode) query.set('data_mode', params.data_mode);
  if (params.window) query.set('window', params.window);
  if (params.store_id) query.set('store_id', params.store_id);
  if (params.sku) query.set('sku', params.sku);
  if (params.status) query.set('status', params.status);
  if (params.priority) query.set('priority', params.priority);
  if (params.category) query.set('category', params.category);
  if (params.search) query.set('search', params.search);
  if (params.limit) query.set('limit', String(params.limit));
  if (params.offset) query.set('offset', String(params.offset));

  const qs = query.toString();
  return apiRequest(`/tickets${qs ? `?${qs}` : ''}`);
}

/**
 * GET /api/tickets/{ticket_id}
 */
export async function getTicket(ticketId) {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}`);
}

/**
 * PATCH /api/tickets/{ticket_id}/status
 * @param {string} ticketId
 * @param {string} status - "Open" | "In Progress" | "Closed"
 * @param {number} expectedVersion
 * @param {string} reason - optional note / justification
 */
export async function updateTicketStatus(ticketId, status, expectedVersion, reason = null) {
  const body = {
    status,
    expected_version: expectedVersion,
  };
  if (reason) {
    body.reason = reason;
  }

  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}/status`, {
    method: 'PATCH',
    body,
  });
}

// =============================================================================
// 7. DASHBOARD & AGGREGATE METRICS
// =============================================================================

/**
 * GET /api/dashboard
 * @param {object} params - { data_mode, window, store_id, sku, status, priority, category }
 */
export async function getDashboard(params = {}) {
  const query = new URLSearchParams();

  if (params.data_mode) query.set('data_mode', params.data_mode);
  if (params.window) query.set('window', params.window);
  if (params.store_id) query.set('store_id', params.store_id);
  if (params.sku) query.set('sku', params.sku);
  if (params.status) query.set('status', params.status);
  if (params.priority) query.set('priority', params.priority);
  if (params.category) query.set('category', params.category);

  const qs = query.toString();
  return apiRequest(`/dashboard${qs ? `?${qs}` : ''}`);
}

// =============================================================================
// 8. NATURAL LANGUAGE ANALYTICS
// =============================================================================

/**
 * POST /api/dashboard/analytics
 * @param {string} question - e.g. "count unresolved tickets by store"
 * @param {object} filters - { data_mode, window, store_id, status, priority }
 * @param {string} analyticsThreadId - optional UUID
 */
export async function queryAnalytics(question, filters = {}, analyticsThreadId = null) {
  const body = {
    question,
    filters: filters || {},
  };
  if (analyticsThreadId) {
    body.analytics_thread_id = analyticsThreadId;
  }

  return apiRequest('/dashboard/analytics', {
    method: 'POST',
    body,
  });
}

// =============================================================================
// 9. POLICY RETRIEVAL
// =============================================================================

/**
 * GET /api/policies/{section_id}
 * @param {string} sectionId - e.g. "02_pos_pricing_returns_policy.md#pos-system-outages"
 */
export async function getPolicy(sectionId) {
  return apiRequest(`/policies/${encodeURIComponent(sectionId)}`);
}

export default {
  getHealth,
  login,
  logout,
  getMe,
  getStores,
  createConversation,
  getConversation,
  sendMessage,
  getDraft,
  createTicket,
  getTickets,
  getTicket,
  updateTicketStatus,
  getDashboard,
  queryAnalytics,
  getPolicy,
  getAuthToken,
  setAuthToken,
  clearAuthToken,
  generateUUID,
};

