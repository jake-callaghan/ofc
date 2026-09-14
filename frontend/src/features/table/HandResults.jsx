import { units } from '../../lib/game.js';
import ScoreBreakdown from './ScoreBreakdown.jsx';

export default function HandResults({ game }) {
  const hand = game.hand;
  const names = game.player_names;

  return (
    <section className="panel result">
      <h2>Hand {hand.number} results</h2>
      <div className="result-units">
        {Object.entries(hand.result.units).map(([p, value]) => (
          <div key={p}>
            <span>{names[p]}</span>
            <strong className={value < 0 ? 'negative' : 'positive'}>
              {units(value)}
              <small> units</small>
            </strong>
            <span>
              {hand.result.evaluations[p].foul
                ? 'Fouled board'
                : game.fantasy[p]
                  ? `Next: ${game.fantasy[p]}-card Fantasyland`
                  : 'Valid board'}
            </span>
          </div>
        ))}
      </div>
      <ScoreBreakdown
        result={hand.result}
        names={names}
      />
    </section>
  );
}
