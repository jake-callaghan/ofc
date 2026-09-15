import { useState } from 'react';
import { api } from '../../lib/api.js';
import { capacity } from '../../lib/game.js';
import { readSaved, save } from '../../lib/storage.js';
import { invitation } from '../../lib/navigation.js';
import ErrorMessage from '../../components/ErrorMessage.jsx';
export default function Lobby({ session, openGame, pendingJoin }) {
  const [mode, setMode] = useState(pendingJoin ? 'join' : 'create');
  const [name, setName] = useState('The weekly game');
  const [rules, setRules] = useState({
    variant: 'pineapple',
    fantasyland: 'progressive',
    moon: true,
    candyland: false,
  });
  const [link, setLink] = useState(pendingJoin || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const saved = readSaved(`ofc.tables.${session.player_id}`, []);
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
  function backup() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(session)], { type: 'application/json' }),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = 'open-face-player-key.json';
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <main className="lobby">
      <div className="page-intro">
        <h1>Tables</h1>
      </div>
      <div className="lobby-grid">
        <section className="panel setup">
          <div
            className="tabs"
            role="tablist"
            aria-label="Table setup"
          >
            <button
              role="tab"
              aria-selected={mode === 'create'}
              onClick={() => setMode('create')}
            >
              Create a table
            </button>
            <button
              role="tab"
              aria-selected={mode === 'join'}
              onClick={() => setMode('join')}
            >
              Join a table
            </button>
          </div>
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
                <label>Game</label>
                <div className="variant-options">
                  {['pineapple', 'classic'].map((variant) => (
                    <button
                      type="button"
                      className={
                        rules.variant === variant ? 'variant active' : 'variant'
                      }
                      key={variant}
                      onClick={() => changeVariant(variant)}
                    >
                      <span>{variant === 'pineapple' ? '♣' : '♠'}</span>
                      <strong>
                        {variant === 'pineapple' ? 'Pineapple' : 'Classic OFC'}
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
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={rules.candyland}
                      disabled={rules.fantasyland === 'off'}
                      onChange={(e) =>
                        setRules({ ...rules, candyland: e.target.checked })
                      }
                    />
                    Candyland
                  </label>
                  <p className="hint">
                    Three flushes: scoop + middle/bottom royalties and 15-card
                    Fantasyland. These are house-rule presets.
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
            <button
              className="primary"
              disabled={busy}
            >
              {busy
                ? 'Just a moment…'
                : mode === 'create'
                  ? 'Create table →'
                  : 'Join table →'}
            </button>
          </form>
        </section>
        <aside>
          <section className="panel recent">
            <h2>Your tables</h2>
            {saved.length ? (
              saved.map((table) => (
                <button
                  className="saved-table"
                  key={table.id}
                  onClick={() => openGame(table.id, table.name)}
                >
                  <span>
                    <strong>{table.name}</strong>
                  </span>
                  <span>↗</span>
                </button>
              ))
            ) : (
              <p className="empty">No saved tables.</p>
            )}
          </section>
          <details className="player-settings">
            <summary>Player key</summary>
            <button
              className="text-button"
              onClick={backup}
            >
              Download player key
            </button>
            <p className="hint">
              Keep it private. Use it to restore your player in another browser.
            </p>
          </details>
        </aside>
      </div>
    </main>
  );
}
