document.addEventListener('DOMContentLoaded', function () {
  /* Mermaid */
  async function renderMermaid() {
    if (!window.mermaid) return;
    var diagrams = document.querySelectorAll('.mermaid');
    if (!diagrams.length) return;

    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'loose',
      theme: isDark ? 'redux-dark-color' : 'redux-color',
    });

    for (var i = 0; i < diagrams.length; i++) {
      var el = diagrams[i];
      if (!el.dataset.src) {
        var rawAttr = el.getAttribute('data-mermaid-src');
        el.dataset.src = rawAttr ? decodeURIComponent(rawAttr).trim() : el.textContent.trim();
      }
      try {
        var id = 'mermaid-svg-' + i + '-' + Date.now();
        var result = await mermaid.render(id, el.dataset.src);
        el.innerHTML = result.svg;
      } catch (err) {
        console.error('Mermaid render error:', err);
      }
    }
  }

  renderMermaid();

  /* Dark-mode toggle */
  var toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var dark = document.documentElement.getAttribute('data-theme') === 'dark';
      document.documentElement.setAttribute('data-theme', dark ? '' : 'dark');
      try {
        localStorage.setItem('theme', dark ? 'light' : 'dark');
      } catch (e) {}
      renderMermaid();
    });
  }
});
