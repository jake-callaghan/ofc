import { useState } from 'react';
import { api } from '../../lib/api.js';
import ErrorMessage from '../../components/ErrorMessage.jsx';
import ActionButton from '../../components/ui/ActionButton.jsx';

export default function Account({ session, onClose, onPasswordSaved }) {
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function save(event) {
    event.preventDefault();
    if (password !== confirmation) {
      setError('Passwords do not match.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const result = await api('/auth/password', null, { password });
      onPasswordSaved(result.message);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function connect() {
    setBusy(true);
    setError('');
    try {
      location.assign((await api('/auth/google', null, { link: true })).url);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }
  return (
    <main className="welcome">
      <section className="panel welcome-form">
        <h1>{session.recovery ? 'Choose a new password' : 'Your account'}</h1>
        <p>
          {session.name} · {session.email}
        </p>
        {!session.recovery && (
          <>
            <p>
              Connected login methods:{' '}
              {session.providers?.join(', ') || 'email'}
            </p>
            {!session.providers?.includes('google') && (
              <button
                className="secondary"
                disabled={busy}
                onClick={connect}
              >
                Connect Google
              </button>
            )}
            <p>
              Adding a login method keeps your player identity, games, and
              history.
            </p>
          </>
        )}
        <form onSubmit={save}>
          <label>
            New password
            <input
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={256}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <label>
            Confirm new password
            <input
              type="password"
              autoComplete="new-password"
              required
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
            />
          </label>
          <p>
            Use at least 12 characters. Saving signs you out on all devices.
          </p>
          <ErrorMessage message={error} />
          <ActionButton disabled={busy}>
            {busy ? 'Saving…' : 'Save password'}
          </ActionButton>
        </form>
        {!session.recovery && (
          <button
            className="text-button"
            onClick={onClose}
          >
            Back to the table
          </button>
        )}
      </section>
    </main>
  );
}
