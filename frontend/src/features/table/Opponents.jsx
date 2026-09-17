import Board from '../../components/cards/Board.jsx';
import FantasylandCelebration from './FantasylandCelebration.jsx';

export default function Opponents({ hand, names, playerId, nextFantasy }) {
  return (
    <div className="opponents">
      {hand.players
        .filter((p) => p !== playerId)
        .map((p) => (
          <section
            className={`opponent ${hand.turn?.player === p ? 'is-turn' : ''}`}
            key={p}
          >
            <div className="opponent-heading">
              <strong>
                <span className="avatar">{names[p]?.[0]}</span>
                {names[p]}
              </strong>
              <span>
                {hand.turn?.player === p
                  ? 'Your opponent is playing'
                  : hand.fantasy[p]
                    ? '✦ Fantasyland'
                    : 'At the table'}
              </span>
            </div>
            <div className="celebration-board">
              {hand.status === 'complete' && nextFantasy[p] > 0 && (
                <FantasylandCelebration key={hand.number} />
              )}
              <Board
                board={hand.boards[p]}
                compact
                hidden={!!hand.fantasy[p] && hand.status !== 'complete'}
              />
            </div>
          </section>
        ))}
    </div>
  );
}
