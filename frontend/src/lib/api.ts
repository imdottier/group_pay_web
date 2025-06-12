import axios from 'axios';

// Create axios instance with default config
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add a request interceptor for authentication
api.interceptors.request.use(
  (config: any) => {
    // Get token from localStorage when in browser
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('token');
      if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error: any) => {
    return Promise.reject(error);
  }
);

// Add a response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  async (error: any) => {
    // Handle 401 errors (unauthorized)
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        // Only redirect if we are NOT already on the login page
        if (window.location.pathname !== '/login') {
          localStorage.removeItem('token');
          window.location.href = '/login';
        } else {
          // If already on login page, don't redirect, let the page handle the 401 error display
          // console.log('401 on login page, not redirecting globally.');
        }
      }
    }
    return Promise.reject(error);
  }
);

export const createBill = (groupId: string, billData: any) => {
    return api.post(`/groups/${groupId}/bills`, billData);
};

export default api; 