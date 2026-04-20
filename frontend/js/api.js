/**
 * api.js — Thin wrapper around fetch for all BuyWise API calls.
 * All methods return parsed JSON or throw an error.
 */

const API_BASE = '/api';

async function apiFetch(url, options = {}) {
  const defaults = {
    headers: { 'Content-Type': 'application/json' },
  };
  const config = { ...defaults, ...options };
  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body);
  }

  const res = await fetch(`${API_BASE}${url}`, config);
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return data;
}

const API = {
  /** GET /api/health/ */
  health: () => apiFetch('/health/'),

  /** POST /api/agent/session/ */
  createSession: (guestId) =>
    apiFetch('/agent/session/', { method: 'POST', body: { guest_id: guestId } }),

  /** GET /api/agent/session/<id>/ */
  getSession: (sessionId) => apiFetch(`/agent/session/${sessionId}/`),

  /** POST /api/agent/ask/ */
  ask: (sessionId, message, guestId) =>
    apiFetch('/agent/ask/', {
      method: 'POST',
      body: { session_id: sessionId, message, guest_id: guestId },
    }),

  /** POST /api/agent/compare/ */
  compare: (sessionId, productIdA, productIdB) =>
    apiFetch('/agent/compare/', {
      method: 'POST',
      body: { session_id: sessionId, product_id_a: productIdA, product_id_b: productIdB },
    }),

  /** POST /api/agent/confirm_purchase/ */
  confirmPurchase: (sessionId, productId, guestId) =>
    apiFetch('/agent/confirm_purchase/', {
      method: 'POST',
      body: { session_id: sessionId, product_id: productId, guest_id: guestId },
    }),

  /** GET /api/orders/<id>/ */
  getOrder: (orderId) => apiFetch(`/orders/${orderId}/`),

  /** GET /api/products/<id>/ */
  getProduct: (productId) => apiFetch(`/products/${productId}/`),
};

window.API = API;
