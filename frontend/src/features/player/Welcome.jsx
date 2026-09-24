import { useState } from 'react';
import { api } from '../../lib/api.js';
import ErrorMessage from '../../components/ErrorMessage.jsx';
import ActionButton from '../../components/ui/ActionButton.jsx';

export default function Welcome({ onSession, enabled, notice }) {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  function rememberReturn() {
    if (location.hash)
      sessionStorage.setItem('ofc.login-return', location.hash);
  }
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    rememberReturn();
    try {
      const result = await api(
        `/auth/${mode}`,
        null,
        mode === 'recover'
          ? { email }
          : { email, password, ...(mode === 'signup' ? { name } : {}) },
      );
      setPassword('');
      if (mode === 'login') onSession(result);
      else setMessage(result.message);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function google() {
    setBusy(true);
    setError('');
    rememberReturn();
    try {
      location.assign((await api('/auth/google', null, {})).url);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }
  function change(next) {
    setMode(next);
    setPassword('');
    setMessage('');
    setError('');
  }
  return (
    <main className="welcome">
      <h1>Open-face Chinese poker</h1>
      <form
        className="panel welcome-form"
        onSubmit={submit}
      >
        <h2>
          {mode === 'signup'
            ? 'Create your account'
            : mode === 'recover'
              ? 'Reset your password'
              : 'Sign in'}
        </h2>
        {!enabled && <p>Account login is not configured yet.</p>}
        {(message || notice) && <p role="status">{message || notice}</p>}
        {mode === 'signup' && (
          <label>
            Display name
            <input
              required
              maxLength={80}
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="nickname"
            />
          </label>
        )}
        <label>
          Email
          <input
            type="email"
            required
            maxLength={254}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </label>
        {mode !== 'recover' && (
          <label>
            Password
            <input
              type="password"
              required
              minLength={mode === 'signup' ? 12 : 1}
              maxLength={256}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={
                mode === 'signup' ? 'new-password' : 'current-password'
              }
            />
          </label>
        )}
        {mode === 'signup' && (
          <p>
            Use at least 12 characters. We’ll email you a confirmation link.
          </p>
        )}
        <ErrorMessage message={error} />
        <ActionButton disabled={busy || !enabled}>
          {busy
            ? 'Please wait…'
            : mode === 'signup'
              ? 'Create account'
              : mode === 'recover'
                ? 'Send reset link'
                : 'Sign in'}
        </ActionButton>
        {mode !== 'recover' && (
          <button
            type="button"
            className="secondary"
            disabled={busy || !enabled}
            onClick={google}
          >
            Continue with Google
          </button>
        )}
        <div className="auth-links">
          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={() => change(mode === 'login' ? 'signup' : 'login')}
          >
            {mode === 'login' ? 'Create an account' : 'Back to sign in'}
          </button>
          {mode === 'login' && (
            <button
              type="button"
              className="text-button"
              disabled={busy}
              onClick={() => change('recover')}
            >
              Forgot password?
            </button>
          )}
        </div>
      </form>
    </main>
  );
}
