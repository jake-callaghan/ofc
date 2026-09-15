import { useState } from 'react';
import ErrorMessage from '../../components/ErrorMessage.jsx';
import { useGame } from './useGame.js';
import History from './History.jsx';
import TableSidebar from './TableSidebar.jsx';
import TableHand from './TableHand.jsx';
import HeaderScores from './HeaderScores.jsx';
export default function Table({ id, session, home }) {
  const { game, connection, error, busy, command } = useGame(id, session.token);
  const [view, setView] = useState('table');
  const [seats, setSeats] = useState(null);
  if (!game)
    return (
      <main className="loading panel">
        <h2>Finding your table…</h2>
        <ErrorMessage message={error} />
        <button
          className="secondary"
          onClick={home}
        >
          Back to tables
        </button>
      </main>
    );
  const hand = game.hand;
  const completedHands =
    game.hand_number - (hand?.status === 'playing' ? 1 : 0);
  const handLabel = hand
    ? `HAND ${String(hand.number).padStart(2, '0')}`
    : 'A FRESH DECK';
  const fantasyLabel =
    game.rules.fantasyland === 'off'
      ? 'No Fantasyland'
      : `${game.rules.fantasyland} Fantasyland`;
  const connectionLabel = {
    live: 'Live table',
    connecting: 'Connecting…',
    offline: 'Reconnecting…',
  }[connection];
  return (
    <main
      className={`table-page ${hand?.status === 'playing' ? 'playing' : ''}`}
    >
      <div className="table-title">
        <div>
          <button
            className="breadcrumb"
            onClick={home}
          >
            ← Tables
          </button>
          <h1>{game.name}</h1>
          <div className="table-subtitle">
            <span className="variant-name">{game.rules.variant}</span>
            <span>{fantasyLabel}</span>
            <span>
              {game.rules.moon ? 'Moon · ' : ''}
              {game.rules.candyland ? 'Candyland · ' : ''}Units
            </span>
          </div>
        </div>
        <div className="table-heading-right">
          <HeaderScores
            game={game}
            playerId={session.player_id}
          />
          <span
            className={`connection ${connection}`}
            role="status"
          >
            <i />
            {connectionLabel}
          </span>
        </div>
      </div>
      <ErrorMessage message={error} />
      <div className="table-layout">
        <div className="table-main">
          <nav className="tabs">
            <button
              className={view === 'table' ? 'active' : ''}
              onClick={() => setView('table')}
            >
              The table
            </button>
            <button
              className={view === 'history' ? 'active' : ''}
              onClick={() => setView('history')}
            >
              Hand history <small>{completedHands}</small>
            </button>
            <span className="hand-number">{handLabel}</span>
          </nav>
          {view === 'history' && (
            <History
              game={game}
              token={session.token}
            />
          )}

          {view === 'table' && (
            <TableHand
              game={game}
              session={session}
              busy={busy}
              connection={connection}
              command={command}
            />
          )}
        </div>
        <TableSidebar
          game={game}
          session={session}
          connection={connection}
          busy={busy}
          command={command}
          seats={seats}
          setSeats={setSeats}
        />
      </div>
    </main>
  );
}
