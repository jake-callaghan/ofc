import { compareRanks } from '../../lib/royalties.js';
import { units } from '../../lib/game.js';

export default function ShowdownComparison({ result, names }) {
  return (
    <div
      className="showdown-comparisons"
      aria-label="Row comparisons"
    >
      {result.pairs.map((pair) => {
        const a = result.evaluations[pair.a];
        const b = result.evaluations[pair.b];
        const special =
          a.candyland || b.candyland
            ? 'Candyland settlement'
            : a.moon || b.moon
              ? 'Moon settlement'
              : a.foul || b.foul
                ? 'Foul settlement'
                : null;
        return (
          <div
            className="showdown-comparison"
            key={`${pair.a}-${pair.b}`}
          >
            <strong>
              {names[pair.a]} vs {names[pair.b]}
            </strong>
            {special ? (
              <span>{special} · row wins do not apply</span>
            ) : (
              <div className="showdown-row-results">
                {['top', 'middle', 'bottom'].map((row, index) => {
                  const win = compareRanks(a.ranks[row], b.ranks[row]);
                  return (
                    <span
                      className="showdown-row-result"
                      key={row}
                      style={{ '--row-index': index }}
                    >
                      <b>{row}</b>{' '}
                      {win === 0
                        ? 'Tie'
                        : win > 0
                          ? names[pair.a]
                          : names[pair.b]}{' '}
                      · {units(win)}
                      <small>{names[pair.a]}'s row units</small>
                    </span>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
