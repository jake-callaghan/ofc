import { useState } from 'react';
import { readSaved, save } from '../../lib/storage.js';
import ErrorMessage from '../../components/ErrorMessage.jsx';
import { useGame } from './useGame.js';
import History from './History.jsx';
import TableSidebar from './TableSidebar.jsx';
import TableHand from './TableHand.jsx';
import TurnTimer from './TurnTimer.jsx';
import HeaderScores from './HeaderScores.jsx';
import TableChat from './TableChat.jsx';
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
  async function leaveTable() {
    if (await command({ type: 'leave' })) {
      const key = `ofc.tables.${session.player_id}`;
      save(
        key,
        readSaved(key, []).filter((table) => table.id !== id),
      );
      home();
    }
  }
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
            {game.rules.orbits && (
              <span>
                {game.orbit_size
                  ? `${game.normal_hands || 0}/${game.orbit_size * game.rules.orbits} ordinary hands`
                  : `${game.rules.orbits} ${game.rules.orbits === 1 ? 'orbit' : 'orbits'}`}
                {game.status === 'complete' ? ' · Complete' : ''}
              </span>
            )}
            {game.rules.turn_seconds && (
              <span>{game.rules.turn_seconds}s turns</span>
            )}
            <span>
              {game.rules.moon ? 'Moon · ' : ''}
              {game.rules.candyland ? 'Candyland · ' : ''}Units
            </span>
          </div>
        </div>
        <div className="table-heading-right">
          <button
            className="secondary"
            disabled={busy || hand?.status === 'playing'}
            title={
              hand?.status === 'playing'
                ? 'You can leave between hands'
                : 'Remove yourself from this table'
            }
            onClick={leaveTable}
          >
            Leave table
          </button>
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
      <TableChat
        key={id}
        game={game}
        session={session}
        connection={connection}
      />
      {hand?.status === 'playing' && hand.fantasy[session.player_id] ? (
        <div className="turn-banner">
          {hand.fantasy_pending?.includes(session.player_id) ||
          hand.turn?.player === session.player_id
            ? 'Arrange your Fantasyland board and confirm when ready'
            : 'Board confirmed · waiting for showdown'}
        </div>
      ) : hand?.turn ? (
        <div className="turn-banner">
          {hand.turn.player === session.player_id
            ? 'Your turn to play'
            : `${game.player_names[hand.turn.player]} is playing`}
          <TurnTimer game={game} />
        </div>
      ) : hand?.status === 'playing' ? (
        <div className="turn-banner">
          Waiting for Fantasyland players to confirm
        </div>
      ) : null}
      {hand?.last_timeout && (
        <p
          className="timeout-notice"
          role="status"
        >
          {game.player_names[hand.last_timeout.player]}'s timer expired — cards
          were placed randomly.
        </p>
      )}
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
