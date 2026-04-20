/**
 * api.js — Thin wrapper around fetch for all BuyWise API calls.
 */

const API_BASE = '/api';

async function apiFetch(url, options = {}) {
  const defaults = { headers: { 'Content-Type': 'application/json' } };
  const config = { ...defaults, ...options };
  if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
    config.body = JSON.stringify(config.body);
  }
  if (config.body instanceof FormData) {
    // Let browser set Content-Type with boundary
    delete config.headers['Content-Type'];
  }

  const res = await fetch(`${API_BASE}${url}`, config);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

const API = {
  health: () => apiFetch('/health/'),

  createSession: (guestId) =>
    apiFetch('/agent/session/', { method: 'POST', body: { guest_id: guestId } }),

  getSession: (sessionId) => apiFetch(`/agent/session/${sessionId}/`),

  ask: (sessionId, message, guestId) =>
    apiFetch('/agent/ask/', {
      method: 'POST',
      body: { session_id: sessionId, message, guest_id: guestId },
    }),

  compare: (sessionId, productIdA, productIdB) =>
    apiFetch('/agent/compare/', {
      method: 'POST',
      body: { session_id: sessionId, product_id_a: productIdA, product_id_b: productIdB },
    }),

  confirmPurchase: (sessionId, productId, guestId) =>
    apiFetch('/agent/confirm_purchase/', {
      method: 'POST',
      body: { session_id: sessionId, product_id: productId, guest_id: guestId },
    }),

  // ⚡ One-tap instant order
  quickOrder: (sessionId, productId, guestId) =>
    apiFetch('/agent/quick_order/', {
      method: 'POST',
      body: { session_id: sessionId, product_id: productId, guest_id: guestId },
    }),

  // 💬 Ask the seller
  askSeller: (productId, question, sessionId) =>
    apiFetch('/agent/ask_seller/', {
      method: 'POST',
      body: { product_id: productId, question, session_id: sessionId },
    }),

  sellerQAHistory: (productId) =>
    apiFetch(`/agent/seller_qa/${productId}/`),

  // 🎬 Video analysis — URL
  analyzeVideo: ({ session_id, video_url, guest_id }) =>
    apiFetch('/agent/analyze_video/', {
      method: 'POST',
      body: { session_id, video_url, guest_id },
    }),

  // 🎬 Video analysis — file upload (multipart)
  analyzeVideoFile: ({ session_id, file, guest_id }) => {
    const form = new FormData();
    form.append('video_file', file);
    form.append('session_id', session_id || '');
    form.append('guest_id', guest_id || '');
    return apiFetch('/agent/analyze_video/', { method: 'POST', body: form });
  },

  getOrder: (orderId) => apiFetch(`/orders/${orderId}/`),
  getProduct: (productId) => apiFetch(`/products/${productId}/`),
};

window.API = API;
