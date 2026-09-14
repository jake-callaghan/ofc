import { useEffect, useState } from 'react';
import { api } from '../../lib/api.js';
import { units } from '../../lib/game.js';
import Board from '../../components/cards/Board.jsx';
import ErrorMessage from '../../components/ErrorMessage.jsx';
import ScoreBreakdown from './ScoreBreakdown.jsx';
export default function History({ game, token }) {
  const [hands, setHands] = useState([]),
    [error, setError] = useState(''),
    [more, setMore] = useState(false),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api(
      `/games/${game.game_id}/hands?limit=50`,
      token,
      undefined,
      controller.signal,
    )
      .then((items) => {
        setHands(items);
        setMore(items.length === 50);
      })
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e.message);
      });
    return () => controller.abort();
  }, [game.game_id, game.hand_number, game.hand?.status, token]);
  async function loadMore() {
    setBusy(true);
    try {
      const items = await api(
        `/games/${game.game_id}/hands?after=${hands.at(-1).number}&limit=50`,
        token,
      );
      setHands([...hands, ...items]);
      setMore(items.length === 50);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel history">
      <h2>Hand history</h2>
      <ErrorMessage message={error} />
      {!hands.length && (
        <p>Completed hands and their scoring breakdowns will appear here.</p>
      )}
      {hands.map((hand) => (
        <details key={hand.number}>
          <summary>
            Hand {hand.number}
            <span>
              {Object.entries(hand.result.units)
                .map(
                  ([id, value]) => `${game.player_names[id]} ${units(value)}`,
                )
                .join(' · ')}
            </span>
          </summary>
          <ScoreBreakdown
            result={hand.result}
            names={game.player_names}
          />
          <div className="history-boards">
            {Object.entries(hand.boards).map(([id, board]) => (
              <div key={id}>
                <h3>
                  {game.player_names[id]}
                  {hand.result.evaluations[id].foul ? ' · Foul' : ''}
                </h3>
                <Board
                  board={board}
                  compact
                />
              </div>
            ))}
          </div>
        </details>
      ))}
      {more && (
        <button
          className="secondary"
          onClick={loadMore}
          disabled={busy}
        >
          Load more hands
        </button>
      )}
    </section>
  );
}
