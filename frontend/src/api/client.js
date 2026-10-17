// API Client for OrderTrofy
// Centralized configuration supporting both development proxy and direct/deployed API URL

const rawBaseUrl = (import.meta.env.VITE_API_URL || '/api/v1').trim();
const BASE_URL = rawBaseUrl.replace(/\/+$/, '');

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('ordertrofy_admin_token') || null;
    this.customerToken = localStorage.getItem('ordertrofy_customer_token') || null;
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem('ordertrofy_admin_token', token);
    } else {
      localStorage.removeItem('ordertrofy_admin_token');
    }
  }

  setCustomerToken(token) {
    this.customerToken = token;
    if (token) {
      localStorage.setItem('ordertrofy_customer_token', token);
    } else {
      localStorage.removeItem('ordertrofy_customer_token');
    }
  }

  async request(endpoint, options = {}) {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    const url = (endpoint.startsWith('http://') || endpoint.startsWith('https://'))
      ? endpoint
      : `${BASE_URL}${cleanEndpoint}`;

    const headers = {
      ...options.headers,
    };

    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    // Isolate credentials: pass customer session for customer routes, and admin session for admin/auth routes
    const isCustomerRoute = cleanEndpoint.startsWith('/customer');
    if (isCustomerRoute) {
      if (this.customerToken) {
        headers['X-Customer-Session'] = this.customerToken;
        headers['Authorization'] = `Bearer ${this.customerToken}`;
      }
    } else {
      if (this.token) {
        headers['X-Admin-Session'] = this.token;
        headers['Authorization'] = `Bearer ${this.token}`;
      }
    }

    const config = {
      ...options,
      headers,
      credentials: options.credentials || 'include',
    };

    try {
      const response = await fetch(url, config);
      let data;
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        let errorDetail =
          (data && data.detail) ||
          (data && data.message) ||
          response.statusText ||
          'حدث خطأ في الاتصال بالخادم';

        if (Array.isArray(errorDetail)) {
          errorDetail = errorDetail.map((item) => item.msg || JSON.stringify(item)).join(' | ');
        } else if (typeof errorDetail === 'object') {
          errorDetail = JSON.stringify(errorDetail);
        }

        throw new Error(errorDetail);
      }

      return data;
    } catch (err) {
      if (err.name === 'TypeError' && err.message.includes('fetch')) {
        console.error(`Network Error [${endpoint}]:`, err.message);
        throw new Error('تعذر الاتصال بالخادم. يرجى التأكد من تشغيل الخادم والاتصال بالشبكة.');
      }
      console.error(`API Error [${endpoint}]:`, err.message);
      throw err;
    }
  }

  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  post(endpoint, body = {}, options = {}) {
    const isFormData = body instanceof FormData;
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body: isFormData ? body : JSON.stringify(body),
    });
  }

  put(endpoint, body = {}, options = {}) {
    const isFormData = body instanceof FormData;
    return this.request(endpoint, {
      ...options,
      method: 'PUT',
      body: isFormData ? body : JSON.stringify(body),
    });
  }

  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' });
  }
}

export const api = new ApiClient();
