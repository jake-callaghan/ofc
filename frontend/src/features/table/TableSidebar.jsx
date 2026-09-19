import { useState } from 'react';
import { capacity } from '../../lib/game.js';
import { readSaved } from '../../lib/storage.js';
import { invitationLink } from '../../lib/navigation.js';
import ErrorMessage from '../../components/ErrorMessage.jsx';
import TableSettings from './TableSettings.jsx';

export default function TableSidebar({
  game,
  session,
  connection,
  busy,
  command,
  seats,
  setSeats,
}) {
  const id = game.game_id;
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState('');
  const invite = readSaved(`ofc.invite.${id}`, null);
  const hand = game.hand,
    owner = game.owner === session.player_id,
    max = capacity(game.rules);
  const selectedSeats = (seats || game.members.slice(0, max)).filter((p) =>
    game.members.includes(p),
  );
  const share = invite ? invitationLink(location.href, id, invite) : '';
  async function copy() {
    try {
      await navigator.clipboard.writeText(share);
      setCopied(true);
      setCopyError('');
    } catch {
      setCopyError('Copy the invitation from the field below.');
    }
  }

  const names = game.player_names;
  const canStart =
    game.status !== 'complete' && (!hand || hand.status === 'complete');
  return (
    <aside className="table-sidebar">
      {owner && (!hand || hand.status === 'complete') && (
        <TableSettings
          key={`${game.game_id}:${game.rules.turn_seconds}:${game.rules.orbits}`}
          game={game}
          busy={busy}
          connection={connection}
          command={command}
        />
      )}
      {game.status === 'complete' && (
        <section className="panel">
          <h2>Game complete</h2>
          <p>Orbit limit reached. Final scores are shown above.</p>
        </section>
      )}
      {canStart && (
        <section className="panel seating">
          <h3>Players</h3>
          {owner ? (
            <>
              {game.members.map((p) => (
                <label
                  className="check"
                  key={p}
                >
                  <input
                    type="checkbox"
                    checked={selectedSeats.includes(p)}
                    disabled={busy}
                    onChange={(e) =>
                      setSeats(
                        e.target.checked
                          ? [...selectedSeats, p]
                          : selectedSeats.filter((x) => x !== p),
                      )
                    }
                  />
                  {names[p]}
                </label>
              ))}
              <button
                className="secondary"
                disabled={
                  busy ||
                  connection !== 'live' ||
                  (game.cpu_players || []).length >= max - 1
                }
                onClick={() => command({ type: 'add_cpu' })}
              >
                + Add CPU player
              </button>
              <p className="hint">
                Choose 2–{max} players. {selectedSeats.length} selected.
              </p>
              <button
                className="primary"
                disabled={
                  selectedSeats.length < 2 ||
                  selectedSeats.length > max ||
                  busy ||
                  connection !== 'live'
                }
                onClick={() =>
                  command({ type: 'start', players: selectedSeats })
                }
              >
                {busy ? 'Dealing…' : 'Deal next hand →'}
              </button>
            </>
          ) : (
            <p>Waiting for the host to deal.</p>
          )}
        </section>
      )}
      {share && (
        <section className="panel invite">
          <button
            className="secondary"
            onClick={copy}
          >
            {copied ? 'Copied ✓' : 'Copy invite link ↗'}
          </button>
          <details>
            <summary>Show invitation</summary>
            <input
              aria-label="Invitation link"
              value={share}
              readOnly
              onFocus={(e) => e.target.select()}
            />
          </details>
          <ErrorMessage message={copyError} />
        </section>
      )}
      <details className="panel royalty-guide">
        <summary>Royalties & rules</summary>
        <p>
          Rows: ±1 unit. Scoop: +3 extra. Foul: −6 plus your opponent’s
          royalties.
        </p>
        <dl>
          <dt>Top pairs 66–AA</dt>
          <dd>1–9</dd>
          <dt>Top trips 222–AAA</dt>
          <dd>10–22</dd>
          <dt>Bottom straight / flush</dt>
          <dd>2 / 4</dd>
          <dt>Full house / quads</dt>
          <dd>6 / 10</dd>
          <dt>Straight / royal flush</dt>
          <dd>15 / 25</dd>
        </dl>
        <p>
          Middle royalties are double the bottom; middle trips earn 2. Bottom ≥
          middle ≥ top.
        </p>
        {game.rules.moon && (
          <p>
            Moon: a valid J-high bottom replaces normal scoring with 20 units.
            Two moon boards tie.
          </p>
        )}
        {game.rules.candyland && (
          <p>
            Candyland: all three rows flush, ignoring row order. Scoop + your
            middle/bottom royalties; opponent royalties do not count. Earn
            15-card Fantasyland. Two Candyland boards tie; Candyland takes
            precedence over moon.
          </p>
        )}
      </details>
    </aside>
  );
}
