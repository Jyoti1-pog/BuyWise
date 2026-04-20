/**
 * agent.js — Bootstraps the BuyWise chat application.
 * Entry point: initialises all modules and starts the session.
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Initialise modules
  OrderModal.init();
  Chat.init();

  // Start or resume session
  await Chat.start();

  // Wire compare bar trigger button
  document.getElementById('compare-trigger-btn')?.addEventListener('click', () => {
    Chat.triggerCompare();
  });

  // Keyboard shortcut: Escape closes modals
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      OrderModal.close();
      OrderModal.closeSuccess();
    }
  });

  // Initial greeting from agent (displayed client-side, no API call)
  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? 'Good morning' :
    hour < 17 ? 'Good afternoon' :
                'Good evening';

  const welcomeMsg = document.getElementById('welcome-greeting');
  if (welcomeMsg) {
    welcomeMsg.textContent = `${greeting}! I'm BuyWise ✨`;
  }
});
