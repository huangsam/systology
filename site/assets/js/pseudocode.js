document.addEventListener('DOMContentLoaded', () => {
  const toggles = document.querySelectorAll('.pseudocode-toggle');
  const closeButtons = document.querySelectorAll('.pseudocode-modal-close');
  const modals = document.querySelectorAll('.pseudocode-modal');

  function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.showModal();
  }

  function closeModal(modal) {
    if (!modal) return;
    modal.close();
  }

  // Open events
  toggles.forEach((btn) => {
    btn.addEventListener('click', () => {
      const modalId = btn.getAttribute('aria-controls');
      openModal(modalId);
    });
  });

  // Close events on buttons
  closeButtons.forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const modal = e.target.closest('.pseudocode-modal');
      closeModal(modal);
    });
  });

  // Close events on background click (light dismiss)
  modals.forEach((modal) => {
    modal.addEventListener('click', (e) => {
      const rect = modal.getBoundingClientRect();
      const isInDialog =
        rect.top <= e.clientY &&
        e.clientY <= rect.top + rect.height &&
        rect.left <= e.clientX &&
        e.clientX <= rect.left + rect.width;
      if (!isInDialog) {
        closeModal(modal);
      }
    });
  });
});
