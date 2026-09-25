import { useState } from 'react';
import ActiveTables from './ActiveTables.jsx';
import { api } from '../../lib/api.js';
import { capacity } from '../../lib/game.js';
import { save } from '../../lib/storage.js';
import { invitation } from '../../lib/navigation.js';
import { randomTableName } from '../../lib/tableName.js';
import ErrorMessage from '../../components/ErrorMessage.jsx';
import ActionButton from '../../components/ui/ActionButton.jsx';
export default function Lobby({ session, openGame, pendingJoin }) {
  const [mode, setMode] = useState(pendingJoin ? 'join' : null);
  const [visibility, setVisibility] = useState('open');
  const [name, setName] = useState(() => randomTableName(session.name));
  const [rules, setRules] = useState({
    variant: 'pineapple',
    fantasyland: 'progressive',
    moon: true,
    candyland: false,
    turn_seconds: null,
    orbits: null,
  });
  const [link, setLink] = useState(pendingJoin || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  function changeVariant(variant) {
    setRules({
      ...rules,
      variant,
      fantasyland: variant === 'classic' ? 'standard' : 'progressive',
    });
  }
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      if (mode === 'create') {
        const result = await api('/games', session.token, {
          name: name.trim(),
          rules,
          visibility,
        });
        save(`ofc.invite.${result.game_id}`, result.invite);
        openGame(result.game_id, result.state.name);
      } else {
        const parsed = invitation(link.trim());
        const result = await api(
          `/games/${encodeURIComponent(parsed.game)}/join`,
          session.token,
          { invite: parsed.invite, request_id: crypto.randomUUID() },
        );
        openGame(parsed.game, result.state.name);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="lobby">
      <div className="page-intro">
        <h1>Lobby</h1>
      </div>
      <div className="lobby-actions">
        <button
          className="primary"
          aria-expanded={mode === 'create'}
          aria-controls="table-setup"
          onClick={() => {
            setMode(mode === 'create' ? null : 'create');
            setError('');
          }}
        >
          Create table
        </button>
        <button
          className="secondary"
          aria-expanded={mode === 'join'}
          aria-controls="table-setup"
          onClick={() => {
            setMode(mode === 'join' ? null : 'join');
            setError('');
          }}
        >
          Join with invite
        </button>
      </div>
      {mode && (
        <div
          className="lobby-grid"
          id="table-setup"
        >
          <section className="panel setup">
            <h2>
              {mode === 'create' ? 'Create a table' : 'Join with an invite'}
            </h2>
            <form onSubmit={submit}>
              {mode === 'create' ? (
                <>
                  <label>
                    Table name
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      maxLength={120}
                      required
                    />
                  </label>
                  <label>
                    Table access
                    <select
                      value={visibility}
                      onChange={(e) => setVisibility(e.target.value)}
                    >
                      <option value="open">Open · anyone can join</option>
                      <option value="private">Private · invite-only</option>
                    </select>
                  </label>
                  <p className="hint">
                    Both are visible in the lobby. Private tables require an
                    invite to join.
                  </p>
                  <label>Game</label>
                  <div className="variant-options">
                    {['pineapple', 'classic'].map((variant) => (
                      <button
                        type="button"
                        className={
                          rules.variant === variant
                            ? 'variant active'
                            : 'variant'
                        }
                        key={variant}
                        onClick={() => changeVariant(variant)}
                      >
                        <span>{variant === 'pineapple' ? '♣' : '♠'}</span>
                        <strong>
                          {variant === 'pineapple'
                            ? 'Pineapple'
                            : 'Classic OFC'}
                        </strong>
                        <small>
                          {variant === 'pineapple'
                            ? 'Draw 3 · keep 2'
                            : 'One card at a time'}
                        </small>
                      </button>
                    ))}
                  </div>
                  <label>
                    Fantasyland
                    <select
                      value={rules.fantasyland}
                      onChange={(e) =>
                        setRules({
                          ...rules,
                          fantasyland: e.target.value,
                          candyland:
                            e.target.value === 'off' ? false : rules.candyland,
                        })
                      }
                    >
                      <option value="standard">Standard</option>
                      {rules.variant === 'pineapple' && (
                        <option value="progressive">
                          Progressive · 14–17 cards
                        </option>
                      )}
                      <option value="off">Off</option>
                    </select>
                  </label>
                  <label>
                    Orbits
                    <select
                      value={rules.orbits ?? ''}
                      onChange={(event) =>
                        setRules({
                          ...rules,
                          orbits: event.target.value
                            ? Number(event.target.value)
                            : null,
                        })
                      }
                    >
                      <option value="">Unlimited</option>
                      {[1, 2, 3, 5, 10].map((count) => (
                        <option
                          key={count}
                          value={count}
                        >
                          {count}
                        </option>
                      ))}
                    </select>
                  </label>
                  <p className="hint">
                    One hand per starting player per orbit. Fantasyland hands
                    are extra.
                  </p>
                  <label>
                    Turn timer
                    <select
                      value={rules.turn_seconds ?? ''}
                      onChange={(event) =>
                        setRules({
                          ...rules,
                          turn_seconds: event.target.value
                            ? Number(event.target.value)
                            : null,
                        })
                      }
                    >
                      {/* <option value="">Off</option> */}
                      <option value="15">15 seconds</option>
                      <option value="30">30 seconds</option>
                      <option value="60">1 minute</option>
                      <option value="120">2 minutes</option>
                      <option value="300">5 minutes</option>
                    </select>
                  </label>
                  <p className="hint">
                    Random placement when time runs out. Fantasyland is untimed.
                  </p>
                  <details open>
                    <summary>
                      House rules <span>Optional</span>
                    </summary>
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={rules.moon}
                        onChange={(e) =>
                          setRules({ ...rules, moon: e.target.checked })
                        }
                      />
                      Shooting the moon
                    </label>
                    <p className="hint">
                      Valid J-high bottom: 20 units per opponent, replacing
                      ordinary scoring.
                    </p>
                  </details>
                  <div className="table-meta">
                    <span>2–{capacity(rules)} active players</span>
                    <span>Units</span>
                  </div>
                </>
              ) : (
                <>
                  <label>
                    Invitation link
                    <textarea
                      value={link}
                      onChange={(e) => setLink(e.target.value)}
                      placeholder="http://…/#join=…"
                      required
                      rows={3}
                    />
                  </label>
                </>
              )}
              <ErrorMessage message={error} />
              <ActionButton disabled={busy}>
                {busy
                  ? 'Just a moment…'
                  : mode === 'create'
                    ? 'Create table →'
                    : 'Join table →'}
              </ActionButton>
            </form>
          </section>
        </div>
      )}
      <ActiveTables
        session={session}
        openGame={openGame}
      />
    </main>
  );
}
