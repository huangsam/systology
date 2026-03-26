document.addEventListener('DOMContentLoaded', function () {
  /* Mermaid */
  if (window.mermaid) {
    mermaid.initialize({
      startOnLoad: true,
      theme: 'base',
      securityLevel: 'loose',
      themeVariables: {
        primaryColor: '#f3f4f6',
        primaryTextColor: '#0f1724',
        primaryBorderColor: '#2563eb',
        lineColor: '#2563eb',
        secondBkgColor: '#ffffff',
        tertiaryTextColor: '#6b7280',
        tertiaryColor: '#e6e9ee',
        noteBkgColor: '#f0f9ff',
        noteBorderColor: '#2563eb',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      },
      flowchart: { useMaxWidth: true, curve: 'linear' },
      sequence: { useMaxWidth: true },
      gantt: { useWidth: undefined },
    });
  }

  /* Dark-mode toggle */
  var toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var dark = document.documentElement.getAttribute('data-theme') === 'dark';
      document.documentElement.setAttribute('data-theme', dark ? '' : 'dark');
      try {
        localStorage.setItem('theme', dark ? 'light' : 'dark');
      } catch (e) {}
    });
  }
});
