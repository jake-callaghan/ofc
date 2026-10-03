import { useEffect, useState } from 'react';
import { api } from '../../lib/api.js';
import { pounds } from '../../lib/money.js';
import ErrorMessage from '../../components/ErrorMessage.jsx';

export default function Leaderboard({ session }) {
  const [players, setPlayers] = useState(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    setPlayers(null);
    async function refresh() {
      try {
        const rows = await api(
          `/leaderboard?limit=20&offset=${offset}`,
          session.token,
          undefined,
          controller.signal,
        );
        if (!controller.signal.aborted) {
          setPlayers(rows);
          setError('');
        }
      } catch (e) {
        if (!controller.signal.aborted) setError(e.message);
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 30000);
      }
    }
    refresh();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [session.token, offset]);

  return (
    <section
      className="leaderboard"
      aria-label="Leaderboard standings"
    >
      <p className="hint">
        Net GBP from participating human-only hands. Hands involving a CPU and
        unpriced historical hands are excluded.
      </p>
      <ErrorMessage message={error} />
      {!players ? (
        <p>Loading scores…</p>
      ) : !players.length ? (
        <p>No scores yet.</p>
      ) : (
        <ol start={offset + 1}>
          {players.map((player) => (
            <li key={player.player_id}>
              <span>
                {player.name}
                {player.player_id === session.player_id ? ' (you)' : ''}
                <small>
                  {player.hands} {player.hands === 1 ? 'hand' : 'hands'}
                </small>
              </span>
              <strong className={player.net_pence < 0 ? 'negative' : ''}>
                {pounds(player.net_pence)}
              </strong>
            </li>
          ))}
        </ol>
      )}
      {(offset > 0 || players?.length === 20) && (
        <div className="lobby-table-actions">
          <button
            className="secondary"
            disabled={!players || offset === 0}
            onClick={() => setOffset(offset - 20)}
          >
            Previous
          </button>
          <button
            className="secondary"
            disabled={!players || players.length < 20}
            onClick={() => setOffset(offset + 20)}
          >
            Next
          </button>
        </div>
      )}
    </section>
  );
}
