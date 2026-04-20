/**
 * chat.js — Message rendering and chat controller. v2.
 * Wires: send, buy (modal), quick-order (toast), compare, seller Q&A, video analysis.
 */

function parseMarkdown(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');
}

function formatTime(date) {
  return new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit' }).format(date);
}

function createBubble(role, content) {
  const row = document.createElement('div');
  row.className = `message-row ${role} animate-fade-in`;
  const avatarHTML =
    role === 'user'
      ? '<div class="message-avatar user">👤</div>'
      : '<div class="message-avatar ai">✨</div>';

  row.innerHTML = `
    ${role === 'user' ? '' : avatarHTML}
    <div class="message-bubble ${role}">
      <span class="bubble-text">${parseMarkdown(content)}</span>
      <span class="timestamp">${formatTime(new Date())}</span>
    </div>
    ${role === 'user' ? avatarHTML : ''}
  `;
  return row;
}

function createTypingIndicator() {
  const row = document.createElement('div');
  row.className = 'message-row typing-indicator';
  row.id = 'typing-indicator';
  row.innerHTML = `
    <div class="message-avatar ai">✨</div>
    <div class="typing-dots"><span></span><span></span><span></span></div>
  `;
  return row;
}

// ─── Chat Controller ──────────────────────────────────────────────────────────

const Chat = {
  _messagesArea:  null,
  _input:         null,
  _sendBtn:       null,
  _welcomeScreen: null,
  _sessionId:     null,
  _guestId:       null,
  _isLoading:     false,

  init() {
    this._messagesArea  = document.getElementById('messages-area');
    this._input         = document.getElementById('chat-input');
    this._sendBtn       = document.getElementById('send-btn');
    this._welcomeScreen = document.getElementById('welcome-screen');

    this._input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendMessage(); }
    });
    this._input.addEventListener('input', () => {
      this._input.style.height = 'auto';
      this._input.style.height = Math.min(this._input.scrollHeight, 120) + 'px';
    });
    this._sendBtn.addEventListener('click', () => this.sendMessage());

    document.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        this._input.value = chip.dataset.query || chip.textContent.trim();
        this.sendMessage();
      });
    });
    document.querySelectorAll('.quick-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        this._input.value = chip.dataset.query || chip.textContent.trim();
        this.sendMessage();
      });
    });

    document.getElementById('new-chat-btn')?.addEventListener('click', () => this.newChat());
    this._checkStatus();
  },

  async _checkStatus() {
    try {
      const health = await API.health();
      const pill = document.getElementById('status-pill');
      if (pill) {
        if (health.gemini === 'configured') {
          pill.innerHTML = '<div class="dot"></div> Gemini AI';
          pill.classList.remove('fallback');
        } else {
          pill.innerHTML = '<div class="dot"></div> Smart Mode';
          pill.classList.add('fallback');
        }
      }
    } catch { /* ignore */ }
  },

  async start() {
    const { sessionId, guestId } = await Session.ensureSession();
    this._sessionId = sessionId;
    this._guestId   = guestId;

    // Pass session to Video and Seller modules
    if (window.Video)  Video.setSession(sessionId);
    if (window.Seller) Seller.setSession(sessionId);
    if (window.Video)  Video.setChatController(this);
    return { sessionId, guestId };
  },

  async newChat() {
    const { sessionId, guestId } = await Session.newSession();
    this._sessionId = sessionId;
    this._guestId   = guestId;
    this._messagesArea.innerHTML = '';
    if (this._welcomeScreen) this._welcomeScreen.style.display = '';
    CompareState.clear();
    if (window.Video)  Video.setSession(sessionId);
    if (window.Seller) Seller.setSession(sessionId);
  },

  hideWelcome() {
    if (this._welcomeScreen) this._welcomeScreen.style.display = 'none';
  },

  appendBubble(role, content) {
    this.hideWelcome();
    const bubble = createBubble(role, content);
    this._messagesArea.appendChild(bubble);
    this._scrollBottom();
    return bubble;
  },

  appendProducts(products) {
    if (!products?.length) return;
    this.hideWelcome();
    const section = Search.renderProductsSection(
      products,
      (p) => this._onBuyClick(p),
      (p) => this._onCompareToggle(p),
      (p) => this._onQuickOrder(p),
    );
    this._messagesArea.appendChild(section);
    this._scrollBottom();
    this._updateSidebar();
  },

  appendComparePanel(productA, productB) {
    const panel = Search.renderComparePanel(productA, productB);
    this._messagesArea.appendChild(panel);
    this._scrollBottom();
  },

  showTyping() {
    this.hideWelcome();
    this._messagesArea.appendChild(createTypingIndicator());
    this._scrollBottom();
  },

  hideTyping() { document.getElementById('typing-indicator')?.remove(); },

  setLoading(loading) {
    this._isLoading      = loading;
    this._sendBtn.disabled = loading;
    this._input.disabled   = loading;
    if (loading) this.showTyping(); else this.hideTyping();
  },

  _scrollBottom() {
    setTimeout(() => { this._messagesArea.scrollTop = this._messagesArea.scrollHeight; }, 50);
  },

  // ─── Send Flow ─────────────────────────────────────────────────────────────

  async sendMessage() {
    const text = this._input.value.trim();
    if (!text || this._isLoading) return;
    this._input.value = '';
    this._input.style.height = 'auto';

    this.appendBubble('user', text);
    this.setLoading(true);

    try {
      const data = await API.ask(this._sessionId, text, this._guestId);
      this.hideTyping();
      if (data.reply) this.appendBubble('ai', data.reply);
      if (data.products?.length) this.appendProducts(data.products);
      this._sessionId = data.session_id || this._sessionId;
      Video.setSession(this._sessionId);
      Seller.setSession(this._sessionId);
    } catch (err) {
      this.hideTyping();
      this.appendBubble('ai', `⚠️ Something went wrong: ${err.message}. Please try again.`);
    } finally {
      this.setLoading(false);
      this._input.focus();
    }
  },

  // ─── Buy Flow (modal) ───────────────────────────────────────────────────────

  _onBuyClick(product) {
    OrderModal.show(product, () => this._executeOrder(product), null);
  },

  async _executeOrder(product) {
    OrderModal.close();
    this.appendBubble('user', `🛒 Go ahead with ${product.name}!`);
    this.setLoading(true);

    try {
      const orderData = await API.confirmPurchase(this._sessionId, product.id, this._guestId);
      this.hideTyping();
      this.appendBubble('ai',
        `✅ **Order Placed!** ${orderData.message}\n\n` +
        `🔖 Ref: \`${orderData.order_ref}\`\n` +
        `💰 ₹${Number(orderData.total).toLocaleString('en-IN')}\n` +
        `📦 Arriving in ${orderData.estimated_delivery_days} days`
      );
      OrderModal.showSuccess(orderData);
      this._addOrderToSidebar(orderData, product);
    } catch (err) {
      this.hideTyping();
      this.appendBubble('ai', `⚠️ Order failed: ${err.message}`);
    } finally {
      this.setLoading(false);
    }
  },

  // ─── Quick Order (one-tap, no modal) ───────────────────────────────────────

  async _onQuickOrder(product) {
    try {
      const orderData = await API.quickOrder(this._sessionId, product.id, this._guestId);

      // Toast instead of modal
      Toast.order(orderData);

      // Quick bubble in chat (non-blocking)
      this.appendBubble('ai',
        `⚡ **Quick order placed!** ${product.name}\n` +
        `🔖 \`${orderData.order_ref}\` · 📦 ${orderData.estimated_delivery_days}d delivery`
      );

      this._addOrderToSidebar(orderData, product);
    } catch (err) {
      Toast.error('Quick order failed', err.message);
      throw err;   // Let caller reset button state
    }
  },

  // ─── Compare Flow ───────────────────────────────────────────────────────────

  _onCompareToggle(product) {
    const bar   = document.getElementById('compare-bar');
    const label = document.getElementById('compare-bar-label');
    if (CompareState.canCompare()) {
      if (bar) bar.style.display = 'flex';
      if (label) label.textContent = CompareState.selected.map(p => p.name).join(' vs ');
    } else {
      if (bar) bar.style.display = CompareState.selected.length ? 'flex' : 'none';
      if (label && CompareState.selected.length === 1)
        label.textContent = `${CompareState.selected[0].name} selected — pick one more`;
    }
  },

  async triggerCompare() {
    if (!CompareState.canCompare()) return;
    const [a, b] = CompareState.selected;
    CompareState.clear();

    const bar = document.getElementById('compare-bar');
    if (bar) bar.style.display = 'none';
    document.querySelectorAll('.card-btn-compare').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.product-card').forEach(c => c.classList.remove('selected'));

    this.appendBubble('user', `Compare ${a.name} vs ${b.name}`);
    this.setLoading(true);

    try {
      const data = await API.compare(this._sessionId, a.id, b.id);
      this.hideTyping();
      this.appendBubble('ai', `Here's a side-by-side comparison of **${a.name}** vs **${b.name}**:`);
      this.appendComparePanel(data.product_a, data.product_b);
    } catch (err) {
      this.hideTyping();
      this.appendBubble('ai', `⚠️ Comparison failed: ${err.message}`);
    } finally {
      this.setLoading(false);
    }
  },

  // ─── Sidebar ────────────────────────────────────────────────────────────────

  _updateSidebar() { /* extend later for session history */ },

  _addOrderToSidebar(orderData, product) {
    const list = document.getElementById('orders-sidebar-list');
    if (!list) return;
    const card = document.createElement('div');
    card.className = 'order-mini-card animate-fade-in';
    card.innerHTML = `
      <div class="order-ref">${orderData.order_ref}</div>
      <div class="order-name">${product.name}</div>
      <div class="order-info">₹${Number(orderData.total).toLocaleString('en-IN')} · ${orderData.estimated_delivery_days}d delivery</div>
    `;
    list.prepend(card);
    document.getElementById('sidebar-empty')?.remove();
  },
};

window.Chat = Chat;
