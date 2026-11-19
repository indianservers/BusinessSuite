export type GoogleSignInState = 'ready' | 'loading' | 'error' | 'unavailable';
export function googleSignInState(input: {firebaseEnabled?: boolean; moduleCount?: number; googleSso: boolean; pending: boolean; failed: boolean}): GoogleSignInState {
  if (input.googleSso || (input.firebaseEnabled && (input.moduleCount || 0) > 0)) return 'ready';
  if (input.pending) return 'loading';
  return input.failed ? 'error' : 'unavailable';
}

export default function GoogleSignInFallback({state, onRetry}: {state: GoogleSignInState; onRetry: () => void}) {
  if (state === 'ready') return null;
  return <div className="suite-login-providers" aria-label="Google sign-in availability">
    <button type="button" className="suite-secondary" disabled>Continue with Google</button>
    <span role="status" aria-live="polite">{state === 'loading' ? 'Checking Google sign-in availability...' : state === 'error' ? 'Google sign-in options could not load. Retry, or use your email and password below.' : 'Google sign-in is not configured for this installation. Use your email and password below.'}</span>
    {state !== 'loading' && <button type="button" className="suite-secondary" onClick={onRetry}>Retry sign-in options</button>}
  </div>;
}
