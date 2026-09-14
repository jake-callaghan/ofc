import { units } from '../../lib/game.js';
export default function ScoreBreakdown({ result, names }) {
  if (!result) return null;
  return (
    <div className="score-breakdown">
      {result.pairs.map((pair) => (
        <div
          className="pair"
          key={`${pair.a}-${pair.b}`}
        >
          <strong>
            {names[pair.a] || 'Player'} <span>vs</span>{' '}
            {names[pair.b] || 'Player'}
          </strong>
          <div className="pair-values">
            {['rows', 'scoop', 'foul', 'royalties', 'special']
              .filter((part) => pair[part] !== 0)
              .map((part) => (
                <span key={part}>
                  {part} <b>{units(pair[part])}</b>
                </span>
              ))}
            <span className="pair-total">
              Total <b>{units(pair.total)} u</b>
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
