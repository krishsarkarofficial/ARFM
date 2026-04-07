/* ═══════════════════════════════════════════════════════════
   ARFM — SHARED JS
   app.js: router, state, OAuth (via backend), utilities
   ═══════════════════════════════════════════════════════════ */

'use strict';

// ─── APP STATE ────────────────────────────────────────────────
const AppState = {
  user: null,          // { email, name, picture }
  accounts: [],        // discovered accounts
  scanProgress: null,  // { current, total, stage }
  requests: {},        // { [accountId]: { status, sentAt, response } }
  scanComplete: false,

  save() {
    try {
      const safe = { accounts: this.accounts, requests: this.requests, scanComplete: this.scanComplete };
      if (this.user) safe.user = { email: this.user.email, name: this.user.name, picture: this.user.picture };
      sessionStorage.setItem('arfm_state', JSON.stringify(safe));
    } catch (e) { }
  },
  load() {
    try {
      const raw = sessionStorage.getItem('arfm_state');
      if (!raw) return;
      const data = JSON.parse(raw);
      if (data.user) this.user = data.user;
      if (data.accounts) this.accounts = data.accounts;
      if (data.requests) this.requests = data.requests;
      if (data.scanComplete !== undefined) this.scanComplete = data.scanComplete;
    } catch (e) { }
  },
  clear() {
    this.user = null; this.accounts = []; this.requests = {};
    this.scanComplete = false; this.scanProgress = null;
    sessionStorage.removeItem('arfm_state');
  }
};

AppState.load();

// ─── CURSOR ───────────────────────────────────────────────────
function initCursor() {
  const cursor = document.getElementById('cursor');
  const ring = document.getElementById('cursor-ring');
  if (!cursor || !ring) return;
  let mx = 0, my = 0, rx = 0, ry = 0;
  document.addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; });
  document.addEventListener('mouseleave', () => { cursor.style.opacity = '0'; ring.style.opacity = '0'; });
  document.addEventListener('mouseenter', () => { cursor.style.opacity = '1'; ring.style.opacity = '1'; });
  ; (function tick() {
    cursor.style.left = mx + 'px'; cursor.style.top = my + 'px';
    rx += (mx - rx) * 0.12; ry += (my - ry) * 0.12;
    ring.style.left = rx + 'px'; ring.style.top = ry + 'px';
    requestAnimationFrame(tick);
  })();
}

// ─── PARTICLES ─────────────────────────────────────────────────
function initParticles() {
  const canvas = document.getElementById('particle-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let w, h;
  const particles = [];
  const PARTICLE_COUNT = 60;
  const CONNECTION_DIST = 120;

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  class Particle {
    constructor() { this.reset(); }
    reset() {
      this.x = Math.random() * w;
      this.y = Math.random() * h;
      this.vx = (Math.random() - 0.5) * 0.4;
      this.vy = (Math.random() - 0.5) * 0.4;
      this.size = Math.random() * 2 + 0.5;
      this.opacity = Math.random() * 0.5 + 0.1;
    }
    update() {
      this.x += this.vx;
      this.y += this.vy;
      if (this.x < 0 || this.x > w) this.vx *= -1;
      if (this.y < 0 || this.y > h) this.vy *= -1;
    }
    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0, 232, 122, ${this.opacity})`;
      ctx.fill();
    }
  }

  for (let i = 0; i < PARTICLE_COUNT; i++) particles.push(new Particle());

  function animate() {
    ctx.clearRect(0, 0, w, h);
    for (const p of particles) { p.update(); p.draw(); }
    // Draw connections
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < CONNECTION_DIST) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(0, 232, 122, ${0.08 * (1 - dist / CONNECTION_DIST)})`;
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(animate);
  }
  animate();
}

// ─── MAGNETIC BUTTONS ────────────────────────────────────────
function initMagnetic() {
  document.querySelectorAll('.magnetic-wrap').forEach(wrap => {
    const btn = wrap.querySelector('.btn') || wrap;
    wrap.addEventListener('mousemove', e => {
      const rect = wrap.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;
      wrap.style.transform = `translate(${x * 0.15}px, ${y * 0.15}px)`;
    });
    wrap.addEventListener('mouseleave', () => {
      wrap.style.transform = 'translate(0, 0)';
    });
  });
}

// ─── TEXT SPLIT REVEAL ───────────────────────────────────────
function initTextReveal() {
  document.querySelectorAll('.split-text').forEach(el => {
    const text = el.textContent;
    el.innerHTML = '';
    text.split('').forEach((char, i) => {
      const span = document.createElement('span');
      span.className = 'text-reveal';
      span.style.animationDelay = (i * 0.03) + 's';
      span.textContent = char === ' ' ? '\u00a0' : char;
      el.appendChild(span);
    });
  });
}

// ─── TOAST ────────────────────────────────────────────────────
function showToast(msg, type = 'success', duration = 3500) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span style="color:var(--${type === 'success' ? 'green' : type === 'error' ? 'red' : 'blue'})">` + icons[type] + `</span><span class="toast-msg">${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.animation = 'fadeIn 0.3s ease reverse'; setTimeout(() => toast.remove(), 300); }, duration);
}

// ─── SCROLL REVEAL ────────────────────────────────────────────
function initReveal() {
  const els = document.querySelectorAll('.reveal');
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); } });
  }, { threshold: 0.08 });
  els.forEach(el => obs.observe(el));
}

// ─── SMOOTH SCROLL ────────────────────────────────────────────
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}

// ─── NAV ACTIVE ───────────────────────────────────────────────
function setNavActive() {
  const path = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a').forEach(a => {
    const href = a.getAttribute('href') || '';
    if (href.includes(path)) a.classList.add('active');
    else a.classList.remove('active');
  });
  // Show/hide auth-dependent nav items
  const userEl = document.getElementById('nav-user-info');
  const signoutEl = document.getElementById('nav-signout');
  const signinEl = document.getElementById('nav-signin');
  if (AppState.user) {
    if (userEl) { userEl.style.display = 'flex'; userEl.querySelector('.user-name').textContent = AppState.user.name || AppState.user.email; }
    if (signoutEl) signoutEl.style.display = 'inline-flex';
    if (signinEl) signinEl.style.display = 'none';
  } else {
    if (userEl) userEl.style.display = 'none';
    if (signoutEl) signoutEl.style.display = 'none';
    if (signinEl) signinEl.style.display = 'inline-flex';
  }
}

// ─── GOOGLE OAUTH (via Backend) ───────────────────────────────
const OAuth = {
  async login() {
    // Redirect to backend /auth/login which returns the Google OAuth URL
    try {
      const resp = await fetch(API_CONFIG.AUTH_LOGIN, { credentials: 'include' });
      const data = await resp.json();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      } else {
        showToast('Failed to get auth URL', 'error');
      }
    } catch (e) {
      showToast('Could not connect to backend. Is it running?', 'error');
      console.error('Auth error:', e);
    }
  },

  async checkStatus() {
    // Check if we have a valid session cookie
    try {
      const resp = await fetch(API_CONFIG.AUTH_STATUS, { credentials: 'include' });
      const data = await resp.json();
      if (data.authenticated && data.user) {
        AppState.user = {
          email: data.user.email || '',
          name: data.user.name || data.user.email || '',
          picture: data.user.picture || '',
        };
        AppState.save();
        return true;
      }
    } catch (e) {
      console.warn('Auth status check failed:', e);
    }
    return false;
  },

  logout() {
    AppState.clear();
    setNavActive();
    showToast('Signed out. All local data cleared.', 'info');
    // Redirect to backend logout to clear the cookie
    window.location.href = API_CONFIG.AUTH_LOGOUT;
  }
};

// ─── LEGAL TEMPLATES ──────────────────────────────────────────
const Templates = {
  gdpr(company, userEmail) {
    const date = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
    return `Subject: Right to Erasure Request – Article 17 GDPR

To the Data Protection Officer / Privacy Team,
${company}

I am writing to formally request the erasure of all personal data you hold about me, in accordance with Article 17 of the General Data Protection Regulation (EU) 2016/679 – the "Right to Erasure."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA SUBJECT DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Email Address:   ${userEmail}
Date of Request: ${date}
Reference:       GDPR Art. 17 Erasure Request

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
I hereby request that ${company}:

1. Permanently delete all personal data associated with the above email address from all your systems, databases, and backups;

2. Cease all processing of my personal data immediately upon receipt of this request;

3. Instruct any third-party data processors or sub-processors to delete my personal data;

4. Confirm in writing that deletion has been completed.

I understand that you are required to respond to this request without undue delay and within one month of receipt (Article 12(3) GDPR), extendable by two further months where necessary.

If you require identity verification, please advise your preferred method. If you intend to refuse this request, please provide the legal basis for refusal under Article 17(3).

Yours faithfully,

A Data Subject
${userEmail}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This request is made pursuant to Regulation (EU) 2016/679 (GDPR), Article 17.
Supervisory authority complaints may be filed with the relevant national Data Protection Authority.`;
  },

  ccpa(company, userEmail) {
    const date = new Date().toLocaleDateString('en-US', { day: 'numeric', month: 'long', year: 'numeric' });
    return `Subject: CCPA Request to Delete Personal Information – California Civil Code § 1798.105

To the Privacy Team / Legal Department,
${company}

Pursuant to the California Consumer Privacy Act (CCPA), California Civil Code § 1798.100 et seq., and specifically § 1798.105 (Right to Delete), I hereby submit a formal request for the deletion of all personal information that ${company} has collected, maintained, or shared about me.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONSUMER DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Email Address:   ${userEmail}
Date of Request: ${date}
Reference:       CCPA § 1798.105 Deletion Request

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
I request that ${company}:

1. Delete all personal information about me that you have collected, purchased, or received from third parties;

2. Direct all service providers who have received my personal information to delete it as well;

3. Confirm in writing that you have complied with this deletion request within the timeframe required by law.

Under CCPA § 1798.105(d), businesses must respond to deletion requests within 45 days of receipt, with a possible 45-day extension upon notice.

If you are unable to verify my identity via the email address above, please advise on your verification process.

Sincerely,

A California Consumer
${userEmail}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Submitted pursuant to California Civil Code §§ 1798.100–1798.199 (CCPA/CPRA).
Non-compliance may be reported to the California Privacy Protection Agency.`;
  },

  dpdpa(company, userEmail) {
    const date = new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
    return `Subject: DPDPA Section 12(3) — Right to Erasure of Personal Data

To the Data Protection Officer / Grievance Officer,
${company}

I am writing to exercise my right to erasure of personal data under Section 12(3) of the Digital Personal Data Protection Act, 2023 (DPDPA) of India.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA PRINCIPAL DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Email Address:   ${userEmail}
Date of Request: ${date}
Reference:       DPDPA 2023, Section 12(3) Erasure Request

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
I hereby withdraw my consent for the processing of my personal data and request that ${company}:

1. Permanently erase all personal data associated with the above email address from all your systems, databases, and records;

2. Direct any data processors or third parties with whom you have shared my personal data to erase it as well;

3. Cease all processing of my personal data immediately upon receipt of this request;

4. Provide written confirmation that the erasure has been completed.

Under the DPDPA 2023, Data Fiduciaries are required to comply with erasure requests within a reasonable timeframe. Failure to comply may result in a complaint to the Data Protection Board of India under Section 27 of the Act.

If you require additional information to verify my identity, please advise.

Yours faithfully,

A Data Principal
${userEmail}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This request is made pursuant to the Digital Personal Data Protection Act, 2023 (Act No. 22 of 2023), Government of India.
Non-compliance may be reported to the Data Protection Board of India.`;
  }
};

// ─── RISK HELPERS ─────────────────────────────────────────────
function riskClass(risk) {
  return { High: 'badge-red', Medium: 'badge-amber', Low: 'badge-green', Critical: 'badge-red' }[risk] || 'badge-dim';
}
function riskColor(risk) {
  return { High: 'var(--red)', Medium: 'var(--amber)', Low: 'var(--green)', Critical: 'var(--red)' }[risk] || 'var(--text-dim)';
}

// ─── ACCOUNT AGE ─────────────────────────────────────────────
function accountAge(dateStr) {
  if (!dateStr || dateStr === 'Unknown') return 'Unknown';
  const d = new Date(dateStr + '-01');
  const now = new Date();
  const months = (now.getFullYear() - d.getFullYear()) * 12 + (now.getMonth() - d.getMonth());
  if (months < 12) return months + ' months';
  const years = Math.floor(months / 12);
  return years + ' year' + (years > 1 ? 's' : '');
}

// ─── FORMAT DATE ──────────────────────────────────────────────
function fmtDate(dateStr) {
  if (!dateStr || dateStr === 'Unknown') return 'Unknown';
  try {
    return new Date(dateStr + '-01').toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  } catch (e) { return dateStr; }
}

// ─── INIT ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initCursor();
  initReveal();
  setNavActive();
  initParticles();
  initMagnetic();
  initTextReveal();
  initSmoothScroll();

  // Check auth status on load (if we have API_CONFIG)
  if (typeof API_CONFIG !== 'undefined' && !AppState.user) {
    await OAuth.checkStatus();
    setNavActive();
  }

  // Nav sign out
  const signoutBtn = document.getElementById('nav-signout');
  if (signoutBtn) signoutBtn.addEventListener('click', e => { e.preventDefault(); OAuth.logout(); });
});
