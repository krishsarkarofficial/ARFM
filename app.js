/* ═══════════════════════════════════════════════════════════
   ARFM — SHARED JS
   app.js: router, state, OAuth, Gmail scanner, utilities
   ═══════════════════════════════════════════════════════════ */

'use strict';

// ─── CONFIG ──────────────────────────────────────────────────
// Replace with your real Google OAuth client ID
const GOOGLE_CLIENT_ID = window.GOOGLE_CLIENT_ID || 'YOUR_GOOGLE_CLIENT_ID';
const GOOGLE_SCOPES = [
  'https://www.googleapis.com/auth/gmail.readonly',
  'https://www.googleapis.com/auth/userinfo.email',
  'https://www.googleapis.com/auth/userinfo.profile'
].join(' ');

// ─── APP STATE ────────────────────────────────────────────────
const AppState = {
  user: null,          // { email, name, picture, accessToken }
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

// ─── GOOGLE OAUTH ─────────────────────────────────────────────
const OAuth = {
  tokenClient: null,

  init() {
    // Google Identity Services (GIS)
    if (!window.google?.accounts?.oauth2) return;
    this.tokenClient = google.accounts.oauth2.initTokenClient({
      client_id: GOOGLE_CLIENT_ID,
      scope: GOOGLE_SCOPES,
      callback: (resp) => this._handleToken(resp),
      error_callback: (err) => {
        console.error('OAuth error', err);
        showToast('Authentication failed. Please try again.', 'error');
        this._onError && this._onError(err);
      }
    });
  },

  login(onSuccess, onError) {
    this._onSuccess = onSuccess;
    this._onError = onError;
    if (!this.tokenClient) {
      showToast('Please configure your Google Client ID to connect.', 'info', 5000);
      onError && onError(new Error('No Google Client ID configured'));
      return;
    }
    this.tokenClient.requestAccessToken({ prompt: 'consent' });
  },

  async _handleToken(resp) {
    if (resp.error) {
      showToast('Auth error: ' + resp.error, 'error');
      this._onError && this._onError(resp);
      return;
    }
    // Fetch user profile
    try {
      const res = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
        headers: { Authorization: 'Bearer ' + resp.access_token }
      });
      const profile = await res.json();
      AppState.user = {
        email: profile.email,
        name: profile.name || profile.email,
        picture: profile.picture,
        accessToken: resp.access_token
      };
      AppState.save();
      this._onSuccess && this._onSuccess(AppState.user);
    } catch (e) {
      showToast('Failed to fetch profile', 'error');
      this._onError && this._onError(e);
    }
  },

  logout() {
    if (window.google?.accounts?.oauth2 && AppState.user?.accessToken) {
      google.accounts.oauth2.revoke(AppState.user.accessToken, () => { });
    }
    AppState.clear();
    setNavActive();
    showToast('Signed out. All local data cleared.', 'info');
    setTimeout(() => location.href = 'index.html', 800);
  }
};

// ─── GMAIL SCANNER ────────────────────────────────────────────
const GmailScanner = {

  // Keyword patterns for signup detection
  SUBJECT_PATTERNS: [
    /welcome to (.+)/i,
    /verify your (email|account|address)/i,
    /confirm your (.+) (account|email|registration)/i,
    /activate your (.+) account/i,
    /your (.+) account (is ready|has been created|was created)/i,
    /get started with (.+)/i,
    /thanks for (signing up|joining|registering)/i,
    /you(\'re| are) (in|registered|signed up)/i,
    /complete your (.+) (registration|signup|sign-up)/i,
    /finish (setting up|creating) your (.+) account/i,
    /please verify your/i,
    /almost there[,!]/i,
    /one more step/i,
    /confirm your subscription/i,
    /account (created|confirmed|activated)/i,
  ],

  SUBJECT_KEYWORDS: [
    'welcome', 'verify', 'confirm', 'activate', 'registration',
    'get started', 'thanks for signing', 'you\'re in', 'account created',
    'email confirmation', 'please confirm', 'subscription confirmed'
  ],

  SENDER_PATTERNS: [
    /noreply@/, /no-reply@/, /donotreply@/, /accounts@/,
    /notifications@/, /hello@/, /hi@/, /welcome@/, /team@/,
    /support@/, /info@/, /mail@/, /mailer@/, /confirm@/,
    /verify@/, /registration@/,
  ],

  // Domains to ignore (common non-signup senders)
  IGNORE_DOMAINS: new Set([
    'google.com', 'gmail.com', 'apple.com', 'microsoft.com',
    'amazon.com', 'amazon.co.uk', 'paypal.com', 'bankofamerica.com',
    'chase.com', 'wellsfargo.com'
  ]),

  // Company name map for known domains
  DOMAIN_MAP: {
    'spotify.com': 'Spotify', 'notion.so': 'Notion', 'canva.com': 'Canva',
    'trello.com': 'Trello', 'mailchimp.com': 'Mailchimp', 'zapier.com': 'Zapier',
    'miro.com': 'Miro', 'slack.com': 'Slack', 'github.com': 'GitHub',
    'gitlab.com': 'GitLab', 'figma.com': 'Figma', 'dropbox.com': 'Dropbox',
    'notion.io': 'Notion', 'typeform.com': 'Typeform', 'airtable.com': 'Airtable',
    'asana.com': 'Asana', 'linear.app': 'Linear', 'notion.site': 'Notion',
    'hubspot.com': 'HubSpot', 'salesforce.com': 'Salesforce', 'adobe.com': 'Adobe',
    'squarespace.com': 'Squarespace', 'wix.com': 'Wix', 'webflow.com': 'Webflow',
    'shopify.com': 'Shopify', 'etsy.com': 'Etsy', 'ebay.com': 'eBay',
    'twitter.com': 'Twitter/X', 'x.com': 'X (Twitter)', 'instagram.com': 'Instagram',
    'facebook.com': 'Facebook', 'linkedin.com': 'LinkedIn', 'pinterest.com': 'Pinterest',
    'reddit.com': 'Reddit', 'discord.com': 'Discord', 'twitch.tv': 'Twitch',
    'medium.com': 'Medium', 'substack.com': 'Substack', 'producthunt.com': 'Product Hunt',
    'devto': 'Dev.to', 'stackoverflow.com': 'Stack Overflow',
    'zoom.us': 'Zoom', 'calendly.com': 'Calendly', 'loom.com': 'Loom',
    'notion.com': 'Notion', 'clickup.com': 'ClickUp', 'monday.com': 'Monday.com',
    'jira.com': 'Jira', 'confluence.com': 'Confluence',
    'heroku.com': 'Heroku', 'netlify.com': 'Netlify', 'vercel.com': 'Vercel',
    'digitalocean.com': 'DigitalOcean', 'aws.amazon.com': 'AWS',
  },

  RISK_MAP: {
    high: ['mailchimp.com', 'hubspot.com', 'salesforce.com', 'facebook.com', 'instagram.com',
      'linkedin.com', 'twitter.com', 'x.com', 'zapier.com', 'shopify.com', 'ebay.com',
      'etsy.com', 'dropbox.com', 'slack.com'],
    low: ['notion.so', 'figma.com', 'linear.app', 'vercel.com', 'netlify.com', 'github.com'],
  },

  async scan(accessToken, onProgress) {
    return await this._realScan(accessToken, onProgress);
  },

  async _realScan(token, onProgress) {
    const found = new Map(); // domain -> account

    onProgress({ stage: 'Connecting to Gmail…', current: 0, total: 100 });

    // Fetch up to 500 messages matching signup patterns
    const queries = [
      'subject:welcome',
      'subject:verify',
      'subject:confirm account',
      'subject:"get started"',
      'subject:"account created"',
      'subject:"thanks for signing"',
    ];

    let messageIds = [];
    for (const q of queries) {
      try {
        const r = await fetch(
          `https://gmail.googleapis.com/gmail/v1/users/me/messages?q=${encodeURIComponent(q)}&maxResults=100`,
          { headers: { Authorization: 'Bearer ' + token } }
        );
        if (!r.ok) throw new Error('Gmail API ' + r.status);
        const data = await r.json();
        if (data.messages) messageIds.push(...data.messages.map(m => m.id));
      } catch (e) { console.warn('Query failed:', q, e); }
    }

    // Deduplicate
    messageIds = [...new Set(messageIds)];
    const total = messageIds.length;
    onProgress({ stage: `Found ${total} candidate emails. Scanning…`, current: 5, total: 100 });

    // Fetch metadata for each (batch in groups of 20)
    for (let i = 0; i < messageIds.length; i++) {
      const id = messageIds[i];
      const pct = 5 + Math.round((i / Math.max(total, 1)) * 80);
      if (i % 5 === 0) onProgress({ stage: `Analyzing email ${i + 1} of ${total}…`, current: pct, total: 100 });

      try {
        const r = await fetch(
          `https://gmail.googleapis.com/gmail/v1/users/me/messages/${id}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date`,
          { headers: { Authorization: 'Bearer ' + token } }
        );
        if (!r.ok) continue;
        const msg = await r.json();
        const headers = {};
        (msg.payload?.headers || []).forEach(h => { headers[h.name.toLowerCase()] = h.value; });

        const from = headers['from'] || '';
        const subject = headers['subject'] || '';
        const date = headers['date'] || '';
        const snippet = msg.snippet || '';

        const result = this._analyzeEmail(from, subject, snippet, date);
        if (result && !found.has(result.domain)) {
          found.set(result.domain, result);
        }
      } catch (e) { /* skip */ }

      // Rate limit: tiny delay every 20
      if (i % 20 === 19) await new Promise(r => setTimeout(r, 100));
    }

    onProgress({ stage: 'Building digital footprint…', current: 92, total: 100 });
    await new Promise(r => setTimeout(r, 400));

    const accounts = [...found.values()].map((a, i) => ({ ...a, id: 'acc_' + i }));
    onProgress({ stage: `Scan complete. ${accounts.length} accounts discovered.`, current: 100, total: 100 });
    return accounts;
  },

  _analyzeEmail(from, subject, snippet, date) {
    // Extract domain from sender
    const emailMatch = from.match(/@([\w.-]+\.\w{2,})/);
    if (!emailMatch) return null;
    let domain = emailMatch[1].toLowerCase();
    // Strip subdomains like mail.spotify.com → spotify.com
    const parts = domain.split('.');
    if (parts.length > 2) domain = parts.slice(-2).join('.');

    if (this.IGNORE_DOMAINS.has(domain)) return null;

    // Score
    let score = 0;
    const subjectLower = subject.toLowerCase();
    const snippetLower = snippet.toLowerCase();

    // Subject pattern match
    if (this.SUBJECT_PATTERNS.some(p => p.test(subject))) score += 0.45;
    else if (this.SUBJECT_KEYWORDS.some(k => subjectLower.includes(k))) score += 0.25;

    // Transactional sender
    if (this.SENDER_PATTERNS.some(p => p.test(from.toLowerCase()))) score += 0.25;

    // Body snippet keywords
    if (['welcome', 'verify', 'confirm', 'activate', 'signed up', 'registration'].some(k => snippetLower.includes(k))) score += 0.2;

    // Known domain bonus
    if (this.DOMAIN_MAP[domain]) score += 0.1;

    if (score < 0.3) return null;

    const company = this._guessCompany(domain);
    const riskScore = this._calcRisk(domain);
    const signupDate = date ? new Date(date).toISOString().slice(0, 7) : 'Unknown';

    return { domain, company, signupDate, confidence: Math.min(score, 0.99), riskScore, from };
  },

  _guessCompany(domain) {
    if (this.DOMAIN_MAP[domain]) return this.DOMAIN_MAP[domain];
    // Capitalize domain name
    const name = domain.split('.')[0];
    return name.charAt(0).toUpperCase() + name.slice(1);
  },

  _calcRisk(domain) {
    if (this.RISK_MAP.high.includes(domain)) return 'High';
    if (this.RISK_MAP.low.includes(domain)) return 'Low';
    return 'Medium';
  },
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
document.addEventListener('DOMContentLoaded', () => {
  initCursor();
  initReveal();
  setNavActive();
  initParticles();
  initMagnetic();
  initTextReveal();
  initSmoothScroll();

  // Init GIS when Google loads
  window.handleGoogleInit = function () { OAuth.init(); };

  // Nav sign out
  const signoutBtn = document.getElementById('nav-signout');
  if (signoutBtn) signoutBtn.addEventListener('click', e => { e.preventDefault(); OAuth.logout(); });
});
