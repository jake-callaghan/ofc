import { units } from '../../lib/game.js';

export default function HeaderScores({ game, playerId }) {
  const players = [...game.members].sort(
    (a, b) => game.balances[b] - game.balances[a],
  );

  return (
    <div
      className="header-scores"
      aria-label="Running scores in units"
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
          {game.fantasy[id] > 0 && (
            <small className="fantasy-badge">✦ {game.fantasy[id]} cards</small>
          )}
        </div>
      ))}
    </div>
  );
}
