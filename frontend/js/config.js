/**
 * config.js — single source of truth for the backend API URL.
 *
 * Locally: leave BACKEND_URL as an empty string so all fetch calls
 *          use relative paths (same origin as the FastAPI server).
 *
 * On Vercel: set this to your Render service URL, e.g.:
 *          const BACKEND_URL = 'https://pulse-backend.onrender.com';
 *
 * Every fetch() in dashboard.js, chat.js, and themes-page.js
 * prepends this value to the path, so changing it here is the only
 * edit required when moving between environments.
 */
const BACKEND_URL = '';   // ← replace with Render URL after deployment
