/**
 * toast.js — Lightweight toast notification system.
 * Used for one-tap order confirmations and other quick feedback.
 */

const Toast = {
  _container: null,

  _getContainer() {
    if (!this._container) {
      this._container = document.createElement("div");
      this._container.id = "toast-container";
      this._container.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        z-index: 1000;
        display: flex;
        flex-direction: column;
        gap: 10px;
        pointer-events: none;
      `;
      document.body.appendChild(this._container);
    }
    return this._container;
  },

  show({ message, type = "success", duration = 4000, subtitle = "" }) {
    const container = this._getContainer();

    const iconMap = {
      success: "✅",
      error: "❌",
      warning: "⚠️",
      info: "ℹ️",
      order: "⚡",
    };

    const colorMap = {
      success: "var(--clr-success)",
      error: "var(--clr-danger)",
      warning: "var(--clr-warning)",
      info: "var(--clr-primary-light)",
      order: "var(--clr-accent)",
    };

    const glowMap = {
      success: "var(--clr-success-glow)",
      error: "rgba(239,68,68,0.2)",
      warning: "var(--clr-accent-glow)",
      info: "var(--clr-primary-glow)",
      order: "var(--clr-accent-glow)",
    };

    const toast = document.createElement("div");
    toast.style.cssText = `
      background: var(--clr-surface-2);
      border: 1px solid ${colorMap[type]};
      border-radius: var(--radius-lg);
      padding: 14px 18px;
      display: flex;
      align-items: flex-start;
      gap: 12px;
      min-width: 300px;
      max-width: 380px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 20px ${glowMap[type]};
      pointer-events: all;
      animation: toastSlideIn 0.35s cubic-bezier(0.34, 1.56, 0.64, 1) both;
      cursor: pointer;
    `;

    toast.innerHTML = `
      <span style="font-size:20px;flex-shrink:0;margin-top:1px">${iconMap[type]}</span>
      <div style="flex:1;min-width:0">
        <div style="font-size:var(--text-sm);font-weight:600;color:var(--clr-text);line-height:1.3">${message}</div>
        ${subtitle ? `<div style="font-size:var(--text-xs);color:var(--clr-text-dim);margin-top:3px">${subtitle}</div>` : ""}
      </div>
      <button style="
        background:none;border:none;color:var(--clr-text-dim);
        font-size:16px;cursor:pointer;flex-shrink:0;padding:0;
        line-height:1;pointer-events:all
      " aria-label="Dismiss">×</button>
    `;

    // Add slide-in animation keyframes if not already added
    if (!document.getElementById("toast-keyframes")) {
      const style = document.createElement("style");
      style.id = "toast-keyframes";
      style.textContent = `
        @keyframes toastSlideIn {
          from { opacity:0; transform:translateX(110%); }
          to   { opacity:1; transform:translateX(0); }
        }
        @keyframes toastSlideOut {
          from { opacity:1; transform:translateX(0); }
          to   { opacity:0; transform:translateX(110%); }
        }
      `;
      document.head.appendChild(style);
    }

    const dismiss = () => {
      toast.style.animation = "toastSlideOut 0.25s ease forwards";
      setTimeout(() => toast.remove(), 260);
    };

    toast.querySelector("button").addEventListener("click", dismiss);
    toast.addEventListener("click", dismiss);

    container.appendChild(toast);

    // Auto-dismiss
    setTimeout(dismiss, duration);

    return toast;
  },

  order(orderData) {
    this.show({
      type: "order",
      message: `⚡ Ordered! ${orderData.product}`,
      subtitle: `Ref: ${orderData.order_ref} · ${orderData.estimated_delivery_days}d delivery · ₹${Number(orderData.total).toLocaleString("en-IN")}`,
      duration: 5000,
    });
  },

  success(message, subtitle = "") {
    this.show({ type: "success", message, subtitle });
  },

  error(message, subtitle = "") {
    this.show({ type: "error", message, subtitle, duration: 6000 });
  },

  info(message, subtitle = "") {
    this.show({ type: "info", message, subtitle });
  },
};

window.Toast = Toast;
