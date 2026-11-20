const BASE = import.meta.env.VITE_API_URL || '/api';
const TOKEN_KEY = 'subsmate_token';

let unauthorizedHandler = () => {};

export class ApiError extends Error {
  constructor(message, status, errors = {}) {
    super(message);
    this.status = status;
    this.errors = errors;
  }
}

function readToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable; session lasts until reload */
  }
  memoryToken = token;
}

let memoryToken = readToken();

export const getToken = () => memoryToken;

export function onUnauthorized(handler) {
  unauthorizedHandler = handler;
}

function buildUrl(path, params) {
  const url = new URL(BASE + path, window.location.origin);
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value);
  });
  return url.toString();
}

async function request(path, { method = 'GET', body, params, raw = false } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (memoryToken) headers.Authorization = `Bearer ${memoryToken}`;

  let response;
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError('Cannot reach the server. Check that the backend is running.', 0);
  }

  if (response.status === 401 && path !== '/auth/login') unauthorizedHandler();
  if (raw && response.ok) return response;
  if (response.status === 204) return null;

  const isJson = (response.headers.get('content-type') || '').includes('application/json');
  const data = isJson ? await response.json() : await response.text();
  if (!response.ok) {
    const message = (isJson && data.error) || `Request failed (${response.status})`;
    throw new ApiError(message, response.status, (isJson && data.errors) || {});
  }
  return data;
}

export const api = {
  get: (path, params) => request(path, { params }),
  post: (path, body = {}) => request(path, { method: 'POST', body }),
  put: (path, body = {}) => request(path, { method: 'PUT', body }),
  del: (path) => request(path, { method: 'DELETE' }),
  async download(path, params, fallbackName) {
    const response = await request(path, { params, raw: true });
    const disposition = response.headers.get('content-disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const blob = await response.blob();
    const href = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = href;
    link.download = match ? match[1] : fallbackName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(href);
  },
};
