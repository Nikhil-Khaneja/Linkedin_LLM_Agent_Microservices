import { useState, useCallback } from 'react';
import axios from 'axios';

export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const call = useCallback(async (method, url, data = null) => {
    setLoading(true);
    setError(null);
    try {
      const config = { method, url };
      if (data) config.data = data;
      const res = await axios(config);
      return res.data;
    } catch (err) {
      const msg = err.response?.data?.error?.message || err.message || 'Request failed';
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { call, loading, error };
}
