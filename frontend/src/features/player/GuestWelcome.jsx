import { useState } from 'react';
import { api } from '../../lib/api.js';
import ErrorMessage from '../../components/ErrorMessage.jsx';
import ActionButton from '../../components/ui/ActionButton.jsx';
export default function Welcome({ onSession }) {
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      onSession(await api('/players', null, { name: name.trim() }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function restore(event) {
    const file = event.target.files[0];
    if (!file) return;
    file
      .text()
      .then((text) => {
        const data = JSON.parse(text);
        if (
          ![data.name, data.token, data.player_id].every(
            (v) => typeof v === 'string' && v.length,
          )
        )
          throw new Error();
        onSession(data);
      })
      .catch(() => setError('That file is not a valid player key.'));
  }
  return (
    <main className="welcome">
      <h1>Open-face Chinese poker</h1>
      <form
        className="panel welcome-form"
        onSubmit={submit}
      >
        <label>
          Display name
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Jamie"
            maxLength={80}
            required
          />
        </label>
        <ErrorMessage message={error} />
        <ActionButton disabled={busy || !name.trim()}>
          {busy ? 'Creating player…' : 'Continue'}
        </ActionButton>
        <label className="restore">
          Restore player key
          <input
            type="file"
            accept="application/json,.json"
            onChange={restore}
          />
        </label>
      </form>
    </main>
  );
}
