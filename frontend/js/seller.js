/**
 * seller.js — Seller Q&A panel: inline product chat with AI seller persona.
 * Opens as an expandable panel below any product card.
 */

const Seller = {
  _sessionId: null,
  _activePanelProductId: null,

  setSession(sessionId) {
    this._sessionId = sessionId;
  },

  // ── Open/close panel ────────────────────────────────────────────────────

  toggle(productId, productName) {
    const panel = document.getElementById(`seller-panel-${productId}`);
    if (!panel) return;

    const isOpen = !panel.classList.contains("hidden");

    // Close any previously open panel
    if (this._activePanelProductId && this._activePanelProductId !== productId) {
      const prevPanel = document.getElementById(`seller-panel-${this._activePanelProductId}`);
      prevPanel?.classList.add("hidden");
    }

    if (isOpen) {
      panel.classList.add("hidden");
      this._activePanelProductId = null;
    } else {
      panel.classList.remove("hidden");
      this._activePanelProductId = productId;
      // Focus the input
      setTimeout(() => {
        const input = document.getElementById(`seller-input-${productId}`);
        input?.focus();
      }, 100);
    }
  },

  // ── Ask a question ───────────────────────────────────────────────────────

  async ask(productId, productName) {
    const inputEl = document.getElementById(`seller-input-${productId}`);
    const question = inputEl?.value?.trim();
    if (!question) return;

    inputEl.value = "";
    const qaList = document.getElementById(`seller-qa-${productId}`);
    if (!qaList) return;

    // Show user question
    const userQ = document.createElement("div");
    userQ.className = "seller-qa-item seller-qa-user";
    userQ.innerHTML = `<span class="seller-qa-q">💬 ${this._escHtml(question)}</span>`;
    qaList.appendChild(userQ);

    // Show loading dots
    const loadingEl = document.createElement("div");
    loadingEl.className = "seller-qa-item seller-qa-loading";
    loadingEl.innerHTML = `
      <div class="seller-typing-dots">
        <span></span><span></span><span></span>
      </div>`;
    qaList.appendChild(loadingEl);
    qaList.scrollTop = qaList.scrollHeight;

    try {
      const data = await API.askSeller(productId, question, this._sessionId);
      loadingEl.remove();

      const answerEl = document.createElement("div");
      answerEl.className = "seller-qa-item seller-qa-answer animate-fade-in";
      answerEl.innerHTML = `
        <div class="seller-avatar">🏪</div>
        <div class="seller-answer-text">${this._parseMarkdown(data.answer)}</div>
      `;
      qaList.appendChild(answerEl);
      qaList.scrollTop = qaList.scrollHeight;
    } catch (err) {
      loadingEl.remove();
      const errEl = document.createElement("div");
      errEl.className = "seller-qa-item seller-qa-error";
      errEl.textContent = "⚠️ " + err.message;
      qaList.appendChild(errEl);
    }
  },

  // ── Util ─────────────────────────────────────────────────────────────────

  _escHtml(str) {
    return str
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  },

  _parseMarkdown(text) {
    return text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`(.+?)`/g, "<code>$1</code>")
      .replace(/\n/g, "<br>");
  },
};

window.Seller = Seller;
