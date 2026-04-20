/**
 * search.js — Product card rendering + compare state + seller panel.
 * v2: adds ⚡ Instant button, 💬 Seller button, and seller Q&A panel.
 */

// ─── Compare State ────────────────────────────────────────────────────────────
const CompareState = {
  selected: [],
  maxItems: 2,

  toggle(productId, productName) {
    const idx = this.selected.findIndex(p => p.id === productId);
    if (idx >= 0) { this.selected.splice(idx, 1); return false; }
    if (this.selected.length >= this.maxItems) this.selected.shift();
    this.selected.push({ id: productId, name: productName });
    return true;
  },

  isSelected(productId) { return this.selected.some(p => p.id === productId); },
  clear() { this.selected = []; },
  canCompare() { return this.selected.length === 2; },
};
window.CompareState = CompareState;

// ─── Helpers ───────────────────────────────────────────────────────────────────

function renderStars(rating) {
  const full = Math.floor(rating || 0);
  const half = (rating || 0) - full >= 0.5 ? 1 : 0;
  const empty = 5 - full - half;
  return [
    ...Array(full).fill('<span class="star">★</span>'),
    ...Array(half).fill('<span class="star">⯨</span>'),
    ...Array(empty).fill('<span class="star empty">☆</span>'),
  ].join('');
}

function topSpecs(specs, max = 3) {
  return Object.entries(specs || {}).slice(0, max)
    .map(([k, v]) => `<span class="spec-pill" title="${k}">${v}</span>`).join('');
}

const CAT_EMOJI = {
  earbuds: '🎧', headphones: '🎵', laptops: '💻', smartphones: '📱',
  air_fryers: '🍗', smartwatches: '⌚', appliances: '🏠',
};
const catEmoji = (cat) => CAT_EMOJI[cat] || '🛍️';

function rankBadge(rank) {
  const labels = { 1: '🥇 Top Pick', 2: '🥈 Runner-up', 3: '🥉 Great Value' };
  const cls    = { 1: 'rank-1', 2: 'rank-2', 3: 'rank-3' };
  return `<div class="card-rank-badge ${cls[rank] || 'rank-other'}">${labels[rank] || `#${rank}`}</div>`;
}

// ─── Main Product Card ─────────────────────────────────────────────────────────

function renderProductCard(product, onBuy, onCompare, onQuickOrder) {
  const card = document.createElement('div');
  card.className = 'product-card';
  card.dataset.productId = product.id;
  if (CompareState.isSelected(product.id)) card.classList.add('selected');

  const imgHTML = product.image_url
    ? `<img src="${product.image_url}" alt="${product.name}" loading="lazy"
         onerror="this.parentElement.innerHTML='<div class=\\'card-image-placeholder\\'>${catEmoji(product.category)}</div>'">`
    : `<div class="card-image-placeholder">${catEmoji(product.category)}</div>`;

  const verdictClass = product.verdict ? 'has-verdict' : '';
  const verdictText  = product.verdict || (product.pros || []).slice(0, 1).join('') || '';
  const compareActive = CompareState.isSelected(product.id) ? 'active' : '';

  card.innerHTML = `
    ${rankBadge(product.rank)}
    <div class="card-image-wrap">${imgHTML}</div>
    <div class="card-body">
      <div class="card-brand">${product.brand || ''}</div>
      <div class="card-name">${product.name}</div>
      <div class="card-price"><span class="currency">₹</span>${Number(product.price).toLocaleString('en-IN')}</div>
      <div class="card-rating">
        <div class="stars">${renderStars(product.rating)}</div>
        <span class="rating-count">${product.review_count ? `(${Number(product.review_count).toLocaleString()})` : ''}</span>
      </div>
      <div class="card-specs">${topSpecs(product.specs)}</div>
      <div class="card-verdict ${verdictClass}">${verdictText}</div>
    </div>
    <div class="card-footer-v2">
      <button class="card-btn-instant" data-product-id="${product.id}" title="⚡ Instant Order — no confirmation needed">⚡</button>
      <button class="card-btn-buy" data-product-id="${product.id}">🛒 Buy</button>
      <button class="card-btn-seller-icon" data-product-id="${product.id}" title="Ask the seller">💬</button>
      <button class="card-btn-compare ${compareActive}" data-product-id="${product.id}" title="Compare">⊞</button>
    </div>
    <div class="seller-panel hidden" id="seller-panel-${product.id}">
      <div class="seller-panel-header">🏪 Ask the Seller — ${product.name}</div>
      <div class="seller-qa-list" id="seller-qa-${product.id}"></div>
      <div class="seller-input-row">
        <input
          type="text"
          class="seller-input"
          id="seller-input-${product.id}"
          placeholder="Ask about specs, compatibility, warranty…"
        >
        <button class="seller-ask-btn" data-product-id="${product.id}" data-product-name="${product.name}">Ask →</button>
      </div>
    </div>
  `;

  // ── Wire events ──
  card.querySelector('.card-btn-buy').addEventListener('click', (e) => {
    e.stopPropagation();
    onBuy(product);
  });

  card.querySelector('.card-btn-instant').addEventListener('click', async (e) => {
    e.stopPropagation();
    const btn = e.currentTarget;
    if (btn.classList.contains('ordering')) return;
    btn.classList.add('ordering');
    btn.textContent = '…';
    card.classList.add('instant-ordered');

    try {
      await onQuickOrder(product);
    } finally {
      btn.classList.remove('ordering');
      btn.textContent = '⚡';
      setTimeout(() => card.classList.remove('instant-ordered'), 1200);
    }
  });

  card.querySelector('.card-btn-seller-icon').addEventListener('click', (e) => {
    e.stopPropagation();
    const btn = e.currentTarget;
    btn.classList.toggle('active');
    Seller.toggle(product.id, product.name);
  });

  card.querySelector('.card-btn-compare').addEventListener('click', (e) => {
    e.stopPropagation();
    const btn = e.currentTarget;
    const added = CompareState.toggle(product.id, product.name);
    btn.classList.toggle('active', added);
    card.classList.toggle('selected', added);
    onCompare(product);
  });

  // Seller ask button
  card.querySelector('.seller-ask-btn').addEventListener('click', async (e) => {
    e.stopPropagation();
    await Seller.ask(product.id, product.name);
  });

  // Seller input — Enter key
  card.querySelector(`.seller-input`).addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      e.stopPropagation();
      await Seller.ask(product.id, product.name);
    }
  });

  return card;
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function renderSkeletonCard() {
  const el = document.createElement('div');
  el.className = 'card-skeleton';
  el.innerHTML = `
    <div class="skeleton-block skeleton-img"></div>
    <div class="skeleton-body">
      <div class="skeleton-block skeleton-line w-40"></div>
      <div class="skeleton-block skeleton-line w-80"></div>
      <div class="skeleton-block skeleton-line w-60"></div>
      <div class="skeleton-block skeleton-line w-40" style="height:20px;"></div>
    </div>`;
  return el;
}

// ─── Products Section ──────────────────────────────────────────────────────────

function renderProductsSection(products, onBuy, onCompareClick, onQuickOrder) {
  const section = document.createElement('div');
  section.className = 'products-section';
  const scroll = document.createElement('div');
  scroll.className = 'products-scroll';
  products.forEach(p => {
    scroll.appendChild(renderProductCard(p, onBuy, onCompareClick, onQuickOrder));
  });
  section.appendChild(scroll);
  return section;
}

// ─── Compare Panel ────────────────────────────────────────────────────────────

function renderComparePanel(productA, productB) {
  const panel = document.createElement('div');
  panel.className = 'compare-panel animate-slide-up';

  function colHTML(p) {
    const specs = Object.entries(p.specs || {})
      .map(([k, v]) => `<div class="compare-attr"><span class="attr-label">${k}</span><span class="attr-value">${v}</span></div>`)
      .join('');
    const pros = (p.pros || []).map(x =>
      `<div class="compare-attr"><span class="attr-label">✅</span><span class="attr-value" style="color:var(--clr-success)">${x}</span></div>`).join('');
    const cons = (p.cons || []).map(x =>
      `<div class="compare-attr"><span class="attr-label">⚠️</span><span class="attr-value" style="color:var(--clr-warning)">${x}</span></div>`).join('');

    return `
      <div class="compare-col">
        <div style="font-weight:700;font-size:var(--text-sm);margin-bottom:8px;color:var(--clr-text)">${p.name}</div>
        <div style="font-size:var(--text-xl);font-weight:800;color:var(--clr-primary-light);margin-bottom:12px">
          ₹${Number(p.price).toLocaleString('en-IN')}
        </div>
        <div style="font-size:var(--text-xs);font-weight:600;color:var(--clr-text-dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">Specs</div>
        ${specs}
        <div style="font-size:var(--text-xs);font-weight:600;color:var(--clr-text-dim);margin:10px 0 6px;text-transform:uppercase;letter-spacing:.05em">Pros & Cons</div>
        ${pros}${cons}
        ${p.verdict ? `<div style="margin-top:10px;font-size:var(--text-xs);font-style:italic;color:var(--clr-success)">${p.verdict}</div>` : ''}
      </div>`;
  }

  panel.innerHTML = colHTML(productA) + colHTML(productB);
  return panel;
}

window.Search = {
  renderProductCard,
  renderProductsSection,
  renderSkeletonCard,
  renderComparePanel,
};
