/**
 * order.js — Order confirmation modal + order success screen.
 */

const OrderModal = {
  _overlay: null,
  _onConfirm: null,
  _onCancel: null,

  init() {
    this._overlay = document.getElementById('order-modal-overlay');
    document.getElementById('order-modal-cancel')?.addEventListener('click', () => this.close());
    document.getElementById('order-modal-confirm')?.addEventListener('click', () => {
      if (this._onConfirm) this._onConfirm();
    });
    this._overlay?.addEventListener('click', (e) => {
      if (e.target === this._overlay) this.close();
    });
  },

  show(product, onConfirm, onCancel) {
    this._onConfirm = onConfirm;
    this._onCancel  = onCancel;

    // Populate product info
    const imgEl = document.getElementById('modal-product-img');
    if (imgEl) {
      imgEl.src = product.image_url || '';
      imgEl.onerror = () => { imgEl.style.display = 'none'; };
    }
    const nameEl = document.getElementById('modal-product-name');
    if (nameEl) nameEl.textContent = product.name;
    const priceEl = document.getElementById('modal-product-price');
    if (priceEl) priceEl.textContent = `₹${Number(product.price).toLocaleString('en-IN')}`;

    this._overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  },

  close() {
    if (this._onCancel) this._onCancel();
    this._overlay?.classList.add('hidden');
    document.body.style.overflow = '';
  },

  showSuccess(orderData) {
    const overlay = document.getElementById('order-success-overlay');
    if (!overlay) return;

    const refEl = document.getElementById('success-order-ref');
    if (refEl) refEl.textContent = orderData.order_ref;

    const delivEl = document.getElementById('success-delivery');
    if (delivEl) delivEl.textContent = `Delivery in ~${orderData.estimated_delivery_days} days`;

    const prodEl = document.getElementById('success-product-name');
    if (prodEl) prodEl.textContent = orderData.product;

    overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // Auto-close after 6 seconds
    setTimeout(() => this.closeSuccess(), 6000);

    document.getElementById('order-success-close')?.addEventListener('click', () => this.closeSuccess());
  },

  closeSuccess() {
    const overlay = document.getElementById('order-success-overlay');
    overlay?.classList.add('hidden');
    document.body.style.overflow = '';
  },
};

window.OrderModal = OrderModal;
