/* ═══════════════════════════════════════════════════════════
   ARFM — API Configuration
   Central config for backend API communication.
   Auto-detects dev vs production environment.
   ═══════════════════════════════════════════════════════════ */

'use strict';

const API_CONFIG = (() => {
  const hostname = window.location.hostname;

  // Production: your Render backend URL (update after first deploy)
  const PRODUCTION_API = 'https://arfm-backend.onrender.com';

  // Development: local FastAPI server
  const DEV_API = 'http://localhost:8000';

  const isProduction = hostname !== 'localhost' && hostname !== '127.0.0.1';
  const BASE_URL = isProduction ? PRODUCTION_API : DEV_API;

  return {
    BASE_URL,
    isProduction,

    // Auth endpoints
    AUTH_LOGIN: `${BASE_URL}/auth/login`,
    AUTH_CALLBACK: `${BASE_URL}/auth/callback`,
    AUTH_LOGOUT: `${BASE_URL}/auth/logout`,
    AUTH_STATUS: `${BASE_URL}/auth/status`,

    // API endpoints
    API_SCAN: `${BASE_URL}/api/scan`,
    API_SEND_REQUEST: `${BASE_URL}/api/send-request`,
    API_PING: `${BASE_URL}/api/ping`,
    HEALTH: `${BASE_URL}/health`,
  };
})();
