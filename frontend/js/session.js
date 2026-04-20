/**
 * session.js — Session and guest ID management.
 * Persists session_id + guest_id in localStorage.
 */

const SESSION_KEY = 'buywise_session_id';
const GUEST_KEY   = 'buywise_guest_id';

function generateId(length = 12) {
  return Array.from(crypto.getRandomValues(new Uint8Array(length)))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

const Session = {
  getGuestId() {
    let id = localStorage.getItem(GUEST_KEY);
    if (!id) {
      id = generateId(8);
      localStorage.setItem(GUEST_KEY, id);
    }
    return id;
  },

  getSessionId() {
    return localStorage.getItem(SESSION_KEY) || null;
  },

  setSessionId(id) {
    localStorage.setItem(SESSION_KEY, id);
  },

  clearSession() {
    localStorage.removeItem(SESSION_KEY);
  },

  async ensureSession() {
    const guestId = this.getGuestId();
    let sessionId = this.getSessionId();

    if (!sessionId) {
      try {
        const data = await API.createSession(guestId);
        sessionId = data.session_id;
        this.setSessionId(sessionId);
      } catch (err) {
        console.error('Failed to create session:', err);
      }
    }
    return { sessionId, guestId };
  },

  async newSession() {
    this.clearSession();
    return this.ensureSession();
  },
};

window.Session = Session;
