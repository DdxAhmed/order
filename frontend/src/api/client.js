// API Client for OrderTrofy

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

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
    const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL}${endpoint}`;
    const headers = {
      ...options.headers,
    };

    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
      headers['X-Admin-Session'] = this.token;
    }
    if (this.customerToken) {
      headers['X-Customer-Session'] = this.customerToken;
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
        const errorDetail =
          (data && data.detail) ||
          (data && data.message) ||
          response.statusText ||
          'حدث خطأ في الاتصال بالخادم';
        throw new Error(typeof errorDetail === 'object' ? JSON.stringify(errorDetail) : errorDetail);
      }

      return data;
    } catch (err) {
      console.error(`API Error [${endpoint}]:`, err.message);
      throw err;
    }
  }

  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  post(endpoint, body, options = {}) {
    const isFormData = body instanceof FormData;
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body: isFormData ? body : JSON.stringify(body),
    });
  }

  put(endpoint, body, options = {}) {
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
