import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/**
 * Call this at the top of every protected page.
 *
 * On mount it calls verifyToken() — which checks:
 *   1. Local JWT expiry (no network, instant)
 *   2. Server-side signature + revocation via POST /auth/verify
 *   3. Auto-refreshes if expired, logs out if refresh also fails
 *
 * Returns { verified: bool } so the page can show a spinner until done.
 *
 * Usage:
 *   const { verified } = useTokenGuard();
 *   if (!verified) return null;   // or a spinner
 */
export default function useTokenGuard() {
  const { verifyToken } = useAuth();
  const navigate        = useNavigate();
  const [verified, setVerified] = useState(false);

  useEffect(() => {
    let cancelled = false;
    verifyToken().then(ok => {
      if (cancelled) return;
      if (!ok) {
        navigate('/login', { replace: true });
      } else {
        setVerified(true);
      }
    });
    return () => { cancelled = true; };
  }, []);

  return { verified };
}
