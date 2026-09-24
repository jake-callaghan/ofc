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
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const result = await api(
        `/auth/${mode}`,
        null,
        { email, password, ...(mode === 'signup' ? { name } : {}) },
      );
      setPassword('');
      onSession(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function change(next) {
    setMode(next);
    setPassword('');
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
            : 'Sign in'}
        </h2>
        {!enabled && <p>Account login is not configured yet.</p>}
        {notice && <p role="status">{notice}</p>}
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
        {mode === 'signup' && (
          <p>
            Use at least 12 characters.
          </p>
        )}
        <ErrorMessage message={error} />
        <ActionButton disabled={busy || !enabled}>
          {busy
            ? 'Please wait…'
            : mode === 'signup'
              ? 'Create account'
              : 'Sign in'}
        </ActionButton>
        <div className="auth-links">
          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={() => change(mode === 'login' ? 'signup' : 'login')}
          >
            {mode === 'login' ? 'Create an account' : 'Back to sign in'}
          </button>
        </div>
      </form>
    </main>
  );
}
