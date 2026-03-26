document.addEventListener('DOMContentLoaded', () => {
  const toggles = document.querySelectorAll('.pseudocode-toggle');
  const closeButtons = document.querySelectorAll('.pseudocode-modal-close');
  const overlays = document.querySelectorAll('.pseudocode-modal-overlay');

  function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    // Set active class to display: flex
    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');

    // Prevent background scrolling and scroll chaining
    document.documentElement.style.overflow = 'hidden';
    document.documentElement.style.overscrollBehavior = 'none';
    document.body.style.overflow = 'hidden';
    document.body.style.overscrollBehavior = 'none';

    // Focus the modal container for accessibility without highlighting the close button
    const content = modal.querySelector('.pseudocode-modal-content');
    if (content) {
      content.setAttribute('tabindex', '-1');
      content.focus();
    }
  }

  function closeModal(modal) {
    if (!modal) return;

    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');

    // Restore scrolling and overscroll behavior
    document.documentElement.style.overflow = '';
    document.documentElement.style.overscrollBehavior = '';
    document.body.style.overflow = '';
    document.body.style.overscrollBehavior = '';

    // Return focus to the toggle button that opened it
    const toggleBtn = document.querySelector(`.pseudocode-toggle[aria-controls="${modal.id}"]`);
    if (toggleBtn) toggleBtn.focus();
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

  // Close events on background click
  overlays.forEach((overlay) => {
    overlay.addEventListener('click', (e) => {
      const modal = e.target.closest('.pseudocode-modal');
      closeModal(modal);
    });
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const activeModal = document.querySelector('.pseudocode-modal.active');
      if (activeModal) closeModal(activeModal);
    }
  });
});
