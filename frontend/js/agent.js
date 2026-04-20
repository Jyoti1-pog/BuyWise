/**
 * agent.js — App bootstrap. v2.
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Init modules
  OrderModal.init();
  Chat.init();
  Video.init();

  // Start session (returns sessionId, guestId)
  await Chat.start();

  // Wire compare bar
  document.getElementById('compare-trigger-btn')?.addEventListener('click', () => {
    Chat.triggerCompare();
  });

  // Wire video toggle button in input area
  // (already handled in Video.init())

  // Escape key: close modals + video panel
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      OrderModal.close();
      OrderModal.closeSuccess();
      Video.closePanel();
    }
  });

  // Dynamic greeting
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const el = document.getElementById('welcome-greeting');
  if (el) el.textContent = `${greeting}! I'm BuyWise ✨`;
});
