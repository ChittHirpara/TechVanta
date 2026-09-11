/**
 * BhoomiScan AI — Centralized API Client
 * Proxied via Vite /api/v1 -> http://127.0.0.1:8000/api/v1
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export function getStoredToken() {
  try {
    const token = sessionStorage.getItem('bhoomi_token');
    return token && token !== 'null' && token !== 'undefined' ? token : null;
  } catch {
    return null;
  }
}

export function setStoredToken(token) {
  if (token) {
    sessionStorage.setItem('bhoomi_token', token);
  } else {
    sessionStorage.removeItem('bhoomi_token');
  }
}

export function getStoredUser() {
  try {
    const raw = sessionStorage.getItem('bhoomi_user');
    return raw && raw !== 'null' && raw !== 'undefined' ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user) {
  if (user) {
    sessionStorage.setItem('bhoomi_user', JSON.stringify(user));
  } else {
    sessionStorage.removeItem('bhoomi_user');
  }
}

export async function apiClient(endpoint, options = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  const headers = { ...(options.headers || {}) };
  const token = getStoredToken();

  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Set Content-Type: application/json if body is not FormData
  if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    const isLoginRequest = url.includes('/auth/login');
    if (isLoginRequest) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Invalid username or password.');
    }
    // Session expired
    setStoredToken(null);
    setStoredUser(null);
    window.dispatchEvent(new CustomEvent('bhoomi:unauthorized'));
    throw new Error('Authentication required. Session expired.');
  }

  if (res.status === 403) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Access forbidden: insufficient permissions.');
  }

  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: res.statusText }));
    let errorMsg = 'Request failed';
    if (typeof errData.detail === 'string') {
      errorMsg = errData.detail;
    } else if (Array.isArray(errData.detail)) {
      errorMsg = errData.detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
    } else if (errData.detail) {
      errorMsg = JSON.stringify(errData.detail);
    }
    throw new Error(errorMsg || `Error ${res.status}: ${res.statusText}`);
  }

  if (res.status === 204) return null;
  return await res.json();
}

/* ── Service Methods ── */
export const authApi = {
  login: (credentials) =>
    apiClient('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    }),
  register: (payload) =>
    apiClient('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getMe: (token) =>
    apiClient('/auth/me', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }),
};

export const dashboardApi = {
  getStats: () => apiClient('/dashboard/stats'),
};

export const documentsApi = {
  list: (params = {}) => {
    const query = new URLSearchParams();
    if (params.page) query.append('page', params.page);
    if (params.pageSize) query.append('page_size', params.pageSize);
    if (params.status) query.append('status', params.status);
    if (params.district) query.append('district', params.district);
    if (params.search) query.append('search', params.search);
    return apiClient(`/documents?${query.toString()}`);
  },
  upload: (formData) =>
    apiClient('/documents/upload', {
      method: 'POST',
      body: formData,
    }),
  get: (id) => apiClient(`/documents/${id}`),
  getIntegrity: (id) => apiClient(`/documents/${id}/integrity`),
  getDuplicates: (id) => apiClient(`/documents/${id}/duplicates`),
  getAudit: (id) => apiClient(`/documents/${id}/audit`),
  exportDilrmp: (id) => apiClient(`/documents/${id}/export/dilrmp`),
  verify: (id) =>
    apiClient(`/documents/${id}/verify`, {
      method: 'POST',
    }),
  reprocess: (id) =>
    apiClient(`/documents/${id}/reprocess`, {
      method: 'POST',
    }),
  patchField: (docId, fieldName, data) =>
    apiClient(`/documents/${docId}/fields/${encodeURIComponent(fieldName)}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  getFileUrl: (id, token) =>
    `${API_BASE}/documents/${id}/file?token=${encodeURIComponent(token || getStoredToken() || '')}`,
  getFileBlob: async (id, token) => {
    const headers = {};
    const accessToken = token || getStoredToken();
    if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
    const res = await fetch(`${API_BASE}/documents/${id}/file`, { headers });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(errData.detail || `Error ${res.status}: ${res.statusText}`);
    }
    return res.blob();
  },
  getCertificateUrl: (id, token) =>
    `${API_BASE}/documents/${id}/certificate?token=${encodeURIComponent(token || getStoredToken() || '')}`,
};

export const integrationsApi = {
  pushLrms: (id) =>
    apiClient(`/integrations/lrms/push/${id}`, {
      method: 'POST',
    }),
  pushGis: (id) =>
    apiClient(`/integrations/gis/push/${id}`, {
      method: 'POST',
    }),
};

/**
 * Connect to SSE EventSource for real-time document extraction pipeline updates
 */
export function createDocumentEventSource(docId, onMessage, onError) {
  const token = getStoredToken();
  const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : '';
  const url = `${API_BASE}/documents/${docId}/events${tokenQuery}`;
  const es = new EventSource(url);

  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      onMessage(data);
    } catch (err) {
      console.error('SSE parse error:', err);
    }
  };

  es.onerror = (e) => {
    if (onError) onError(e);
  };

  return es;
}
