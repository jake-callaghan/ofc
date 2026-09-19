import { useState } from 'react';

export default function TableSettings({ game, busy, connection, command }) {
  const [timer, setTimer] = useState(game.rules.turn_seconds ?? '');
  const [orbits, setOrbits] = useState(game.rules.orbits ?? '');
  const changed =
    (timer === '' ? null : Number(timer)) !== game.rules.turn_seconds ||
    (orbits === '' ? null : Number(orbits)) !== game.rules.orbits;

  function submit(event) {
    event.preventDefault();
    command({
      type: 'update_settings',
      turn_seconds: timer === '' ? null : Number(timer),
      orbits: orbits === '' ? null : Number(orbits),
    });
  }

  return (
    <details className="panel table-settings">
      <summary>Table settings</summary>
      <form onSubmit={submit}>
        <label>
          Turn timer (seconds)
          <input
            type="number"
            min="10"
            max="300"
            step="1"
            value={timer}
            placeholder="Off"
            onChange={(event) => setTimer(event.target.value)}
          />
        </label>
        <label>
          Orbit limit
          <input
            type="number"
            min="1"
            max="100"
            step="1"
            value={orbits}
            placeholder="Unlimited"
            onChange={(event) => setOrbits(event.target.value)}
          />
        </label>
        <p className="hint">
          Leave blank for no limit. Orbits count from the start of this game;
          completed hands still count.
        </p>
        <button
          className="secondary"
          disabled={busy || connection !== 'live' || !changed}
        >
          Save settings
        </button>
      </form>
    </details>
  );
}
