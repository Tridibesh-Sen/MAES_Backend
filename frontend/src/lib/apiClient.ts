import axios from 'axios';
import { supabase } from './supabaseClient';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
});

// Automatically inject the Supabase JWT token or guest token into request headers
api.interceptors.request.use(
  async (config) => {
    try {
      let token = null;
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        token = session.access_token;
      } else {
        const demo = localStorage.getItem('maes_demo_session');
        if (demo) {
          try {
            token = JSON.parse(demo).access_token || 'DEMO_USER_TOKEN';
          } catch {
            token = 'DEMO_USER_TOKEN';
          }
        }
      }
      if (token) {
        if (config.headers && typeof (config.headers as any).set === 'function') {
          (config.headers as any).set('Authorization', `Bearer ${token}`);
        } else if (config.headers) {
          (config.headers as any)['Authorization'] = `Bearer ${token}`;
        }
      }
    } catch (e) {
      console.warn("Could not retrieve session for API authentication header:", e);
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;
