import ScoreBreakdown from './ScoreBreakdown.jsx';
import AnimatedUnits from '../../effects/AnimatedUnits.jsx';
import ShowdownComparison from './ShowdownComparison.jsx';

export default function HandResults({ game }) {
  const hand = game.hand;
  const names = game.player_names;

  return (
    <section className="panel result showdown-results">
      <h2>Hand {hand.number} results</h2>
      <div className="result-units">
        {Object.entries(hand.result.units).map(([p, value]) => (
          <div key={p}>
            <span>{names[p]}</span>
            <strong className={value < 0 ? 'negative' : 'positive'}>
              <AnimatedUnits
                value={value}
                delay={1200}
              />
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
      <details className="showdown-details">
        <summary>Row-by-row comparison</summary>
        <ShowdownComparison
          result={hand.result}
          names={names}
        />
      </details>
    </section>
  );
}
