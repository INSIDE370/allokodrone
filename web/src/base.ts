/** Base path Vite (ex. `/` ou `/allokodrone/`). */
export const BASE = import.meta.env.BASE_URL || "/";

/** Backend API (tunnel Cloudflare en prod GitHub Pages). */
export const API_BASE = String(import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");

export function asset(path: string) {
  const clean = path.startsWith("/") ? path.slice(1) : path;
  return `${BASE}${clean}`;
}

export function apiUrl(path: string) {
  const clean = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${clean}`;
}

export function adminUrl(path = "/admin") {
  if (API_BASE) return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  return path;
}
