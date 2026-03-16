/* nav.js — injects navigation into every page */
(function() {
  const NAV_HTML = `
<nav class="nav" id="main-nav">
  <a href="index.html" class="nav-logo">
    <svg width="26" height="26" viewBox="0 0 30 30" fill="none">
      <path d="M15 2L3 8v9c0 6.5 5 12.5 12 14 7-1.5 12-7.5 12-14V8L15 2z" fill="rgba(0,232,122,0.1)" stroke="var(--green)" stroke-width="1.5"/>
      <path d="M10 15l4 4 6-7" stroke="var(--green)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <span class="nav-logo-text">AR<em>F</em>M</span>
  </a>

  <ul class="nav-links">
    <li><a href="index.html">Home</a></li>
    <li><a href="connect.html">Connect</a></li>
    <li><a href="scan.html">Scan</a></li>
    <li><a href="dashboard.html">Dashboard</a></li>
    <li><a href="requests.html">Requests</a></li>
    <li><a href="tracker.html">Tracker</a></li>
  </ul>

  <div class="nav-right">
    <div class="nav-user" id="nav-user-info" style="display:none">
      <span class="nav-user-dot"></span>
      <span class="user-name"></span>
    </div>
    <a href="connect.html" class="btn btn-outline btn-sm" id="nav-signin">Sign In</a>
    <button class="btn btn-ghost btn-sm" id="nav-signout" style="display:none">Sign Out</button>
  </div>
</nav>
<div id="cursor"></div>
<div id="cursor-ring"></div>
<div id="toast-container"></div>
`;
  // Insert at top of body
  const wrapper = document.createElement('div');
  wrapper.innerHTML = NAV_HTML;
  document.body.insertBefore(wrapper, document.body.firstChild);
})();
