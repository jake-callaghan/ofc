import { units } from '../../lib/game.js';
import { pounds } from '../../lib/money.js';

export default function HeaderScores({ game, playerId }) {
  const players = Object.keys(game.balances).sort(
    (a, b) => game.balances[b] - game.balances[a],
  );

  return (
    <div
      className="header-scores"
      aria-label="Running scores in units and GBP"
    >
      {players.map((id) => (
        <div
          className="header-score"
          key={id}
        >
          <span>{game.player_names[id]}</span>
          <strong className={game.balances[id] < 0 ? 'negative' : ''}>
            {units(game.balances[id])}
          </strong>
          <small
            className="gbp-score"
            title="Net GBP for hands with a recorded unit value"
          >
            {pounds(game.gbp_balances?.[id] ?? 0)}
          </small>
          {game.fantasy[id] > 0 && (
            <small className="fantasy-badge">✦ {game.fantasy[id]} cards</small>
          )}
        </div>
      ))}
    </div>
  );
}
