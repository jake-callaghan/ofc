import { useState } from 'react';
import useTurnTimer from './useTurnTimer.js';
import {
  assignCard,
  emptyBoard,
  placement,
  proposeDiscards,
} from '../../lib/game.js';
import Card from '../../components/cards/Card.jsx';
import Board from '../../components/cards/Board.jsx';
export default function TurnEditor({
  game,
  session,
  command,
  busy,
  connected,
}) {
  const secondsLeft = useTurnTimer(game);
  const timedOut = secondsLeft === 0;
  const hand = game.hand;
  const draw = hand.draws[session.player_id] || [];
  const board = hand.boards[session.player_id] || emptyBoard();
  const [draft, setDraft] = useState({}),
    [selected, setSelected] = useState(null);
  const myTurn = hand.turn?.player === session.player_id;
  const keep = myTurn
    ? hand.turn.keep
    : hand.fantasy[session.player_id]
      ? 13
      : 5;
  const proposedDraft = proposeDiscards(draw, draft, keep);
  const value = placement(draw, proposedDraft, keep, board);
  const move = (row) => {
    if (!selected) return;
    const next = assignCard(draft, selected, row, board);
    if (next !== draft) {
      setDraft(next);
      setSelected(null);
    }
  };
  const remove = (card) => {
    setDraft(assignCard(draft, card, null, board));
    setSelected(card);
  };
  const canEdit = !busy && connected;
  const unassignedCards = draw.filter((card) => !proposedDraft[card]);
  const discardedCards = draw.filter(
    (card) => proposedDraft[card] === 'discard',
  );
  const discardCount = draw.length - keep;
  const waitingMessage =
    hand.status === 'complete'
      ? 'Hand complete.'
      : `${game.player_names[hand.turn?.player] || 'Another player'} is arranging their cards.`;

  function resetPlacement() {
    setDraft({});
    setSelected(null);
  }

  return (
    <section className={`my-table ${myTurn ? 'is-turn' : ''}`}>
      <div className="my-table-heading">
        <div>
          <h2>Your hand</h2>
        </div>
        <span className={`pill ${myTurn ? 'accent' : ''}`}>
          {myTurn
            ? 'Your turn'
            : hand.status === 'complete'
              ? 'Complete'
              : 'Waiting'}
        </span>
      </div>
      <Board
        board={board}
        draft={draft}
        selected={selected}
        editable={draw.length > 0 && canEdit}
        move={move}
        remove={remove}
      />
      {draw.length > 0 ? (
        <div className="draw-area">
          <div className="draw-heading">
            <strong>
              {hand.fantasy[session.player_id] ? 'Fantasyland' : 'Your draw'}
            </strong>
            <span>
              Place {keep}
              {discardCount > 0 ? ` · discard ${discardCount}` : ''}
            </span>
          </div>
          <p className="hint">
            {myTurn
              ? 'Select a card, then a row.'
              : 'Arrange your cards while you wait for your turn.'}
          </p>
          <div className="draw-cards">
            {unassignedCards.map((card) => (
              <Card
                key={card}
                card={card}
                selected={selected === card}
                onClick={
                  canEdit
                    ? () => setSelected(selected === card ? null : card)
                    : undefined
                }
              />
            ))}
            {unassignedCards.length === 0 && (
              <p className="all-set">Ready to confirm.</p>
            )}
          </div>
          {discardedCards.length > 0 && (
            <div className="discard-zone">
              <span className="discard-label">
                {discardedCards.length === 1
                  ? 'Proposed discard'
                  : 'Proposed discards'}
              </span>
              {discardedCards.map((card) => (
                <Card
                  small
                  draft
                  card={card}
                  key={card}
                  selected={selected === card}
                  ariaLabel={`${card}, proposed discard; select to place instead`}
                  onClick={
                    canEdit
                      ? () => setSelected(selected === card ? null : card)
                      : undefined
                  }
                />
              ))}
            </div>
          )}
          <div className="turn-actions">
            <button
              className="text-button"
              disabled={busy || !Object.keys(draft).length}
              onClick={resetPlacement}
            >
              Reset placement
            </button>
            <button
              className="primary"
              disabled={!myTurn || timedOut || !value || busy || !connected}
              onClick={() => command(value)}
            >
              {busy
                ? 'Confirming…'
                : myTurn
                  ? 'Confirm placement →'
                  : 'Waiting for your turn'}
            </button>
          </div>
        </div>
      ) : (
        <p className="waiting">{waitingMessage}</p>
      )}
    </section>
  );
}
