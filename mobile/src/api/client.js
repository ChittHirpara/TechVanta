import * as SecureStore from 'expo-secure-store';
import Constants from 'expo-constants';
import { Platform } from 'react-native';
import EventSource from 'react-native-sse';

let customApiBaseUrl = null;

export async function loadSavedApiBaseUrl() {
  try {
    const saved = await SecureStore.getItemAsync('bhoomi_custom_api_url');
    if (saved && saved.startsWith('http')) {
      customApiBaseUrl = saved;
      return saved;
    }
  } catch (_) {}
  return getApiBaseUrl();
}

export async function setCustomApiBaseUrl(url) {
  if (url && url.trim().startsWith('http')) {
    customApiBaseUrl = url.trim().replace(/\/+$/, '');
    if (!customApiBaseUrl.endsWith('/api/v1')) {
      customApiBaseUrl += '/api/v1';
    }
    try {
      await SecureStore.setItemAsync('bhoomi_custom_api_url', customApiBaseUrl);
    } catch (_) {}
  }
}

const LAN_IP_DEFAULT = 'http://192.168.1.113:8000/api/v1';
const DEFAULT_API_BASE = Platform.OS === 'web' ? 'http://localhost:8000/api/v1' : LAN_IP_DEFAULT;

export function getApiBaseUrl() {
  if (customApiBaseUrl) {
    return customApiBaseUrl;
  }
  if (process.env.EXPO_PUBLIC_API_BASE_URL) {
    return process.env.EXPO_PUBLIC_API_BASE_URL;
  }
  // Auto-detect host IP when running via Expo Go on physical device
  const hostUri =
    Constants.expoConfig?.hostUri ||
    Constants.expoGoConfig?.debuggerHost ||
    Constants.manifest?.debuggerHost ||
    Constants.manifest2?.extra?.expoGo?.debuggerHost ||
    (typeof Constants.linkingUri === 'string' && Constants.linkingUri.includes('://')
      ? Constants.linkingUri.split('://')[1]?.split('/')[0]
      : null);

  if (hostUri) {
    const host = hostUri.split(':')[0];
    if (host && host !== 'localhost' && host !== '127.0.0.1' && host !== '10.0.2.2') {
      return `http://${host}:8000/api/v1`;
    }
  }
  return DEFAULT_API_BASE;
}

// In-memory fallback for web/simulator if SecureStore is unavailable
const memoryStore = new Map();

export async function getStoredToken() {
  try {
    const token = await SecureStore.getItemAsync('bhoomi_token');
    return token && token !== 'null' && token !== 'undefined' ? token : memoryStore.get('bhoomi_token') || null;
  } catch (err) {
    return memoryStore.get('bhoomi_token') || null;
  }
}

export async function setStoredToken(token) {
  try {
    if (token) {
      await SecureStore.setItemAsync('bhoomi_token', token);
      memoryStore.set('bhoomi_token', token);
    } else {
      await SecureStore.deleteItemAsync('bhoomi_token');
      memoryStore.delete('bhoomi_token');
    }
  } catch (err) {
    if (token) memoryStore.set('bhoomi_token', token);
    else memoryStore.delete('bhoomi_token');
  }
}

export async function getStoredUser() {
  try {
    const raw = await SecureStore.getItemAsync('bhoomi_user');
    if (raw && raw !== 'null' && raw !== 'undefined') {
      return JSON.parse(raw);
    }
    const memRaw = memoryStore.get('bhoomi_user');
    return memRaw ? JSON.parse(memRaw) : null;
  } catch (err) {
    const memRaw = memoryStore.get('bhoomi_user');
    return memRaw ? JSON.parse(memRaw) : null;
  }
}

export async function setStoredUser(user) {
  try {
    if (user) {
      const str = JSON.stringify(user);
      await SecureStore.setItemAsync('bhoomi_user', str);
      memoryStore.set('bhoomi_user', str);
    } else {
      await SecureStore.deleteItemAsync('bhoomi_user');
      memoryStore.delete('bhoomi_user');
    }
  } catch (err) {
    if (user) memoryStore.set('bhoomi_user', JSON.stringify(user));
    else memoryStore.delete('bhoomi_user');
  }
}

// Global authorization failure listener callback
let onUnauthorizedCallback = null;
export function setUnauthorizedHandler(handler) {
  onUnauthorizedCallback = handler;
}

// Helper to parse JWT payload without external library
export function parseJwt(token) {
  try {
    if (!token) return null;
    const parts = token.split('.');
    if (parts.length < 2) return null;
    let base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4) {
      base64 += '=';
    }
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

export function isTokenExpired(token) {
  const payload = parseJwt(token);
  if (!payload || !payload.exp) return false;
  const now = Math.floor(Date.now() / 1000);
  return payload.exp < now;
}

export async function apiClient(endpoint, options = {}) {
  const apiBase = getApiBaseUrl();
  const url = endpoint.startsWith('http') ? endpoint : `${apiBase}${endpoint}`;
  const headers = { ...(options.headers || {}) };

  const token = await getStoredToken();
  if (token) {
    if (isTokenExpired(token)) {
      await setStoredToken(null);
      await setStoredUser(null);
      if (onUnauthorizedCallback) {
        onUnauthorizedCallback('Session expired. Please log in again.');
      }
      throw new Error('Session expired. Please log in again.');
    }
    if (!headers['Authorization']) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  // Set Content-Type: application/json if body is not FormData
  if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    const errData = await res.json().catch(() => ({}));
    if (endpoint.includes('/auth/login')) {
      throw new Error(errData.detail || 'Invalid username or password.');
    }
    await setStoredToken(null);
    await setStoredUser(null);
    if (onUnauthorizedCallback) {
      onUnauthorizedCallback('Session expired. Please log in again.');
    }
    throw new Error(errData.detail || 'Authentication required. Session expired.');
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

/**
 * Upload FormData with real-time percentage progress callback using XMLHttpRequest
 */
export async function uploadWithProgress(formData, onProgress) {
  const apiBase = getApiBaseUrl();
  const url = `${apiBase}/documents/upload`;
  const token = await getStoredToken();

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);

    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }

    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100);
          onProgress(percentComplete);
        }
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response = JSON.parse(xhr.responseText);
          resolve(response);
        } catch (e) {
          resolve({ id: null, raw: xhr.responseText });
        }
      } else {
        try {
          const errRes = JSON.parse(xhr.responseText);
          reject(new Error(errRes.detail || `Upload failed with status ${xhr.status}`));
        } catch (e) {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      }
    };

    xhr.onerror = () => {
      reject(new Error('Network upload error. Please check connectivity.'));
    };

    xhr.send(formData);
  });
}

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
  getFileUrl: async (id, overrideToken) => {
    const token = overrideToken || (await getStoredToken()) || '';
    return `${getApiBaseUrl()}/documents/${id}/file?token=${encodeURIComponent(token)}`;
  },
};

export const notificationsApi = {
  getNotifications: (limit = 20) => apiClient(`/documents/notifications?limit=${limit}`),
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
export async function createDocumentEventSource(docId, onMessage, onError) {
  const token = await getStoredToken();
  const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : '';
  const url = `${getApiBaseUrl()}/documents/${docId}/events${tokenQuery}`;

  const es = new EventSource(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  es.addEventListener('message', (e) => {
    try {
      if (e.data) {
        const data = JSON.parse(e.data);
        onMessage(data);
      }
    } catch (err) {
      console.warn('SSE parse error:', err);
    }
  });

  es.addEventListener('error', (e) => {
    if (onError) onError(e);
  });

  return es;
}
