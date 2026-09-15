import useTurnTimer from './useTurnTimer.js';

export default function TurnTimer({ game }) {
  const seconds = useTurnTimer(game);
  if (seconds === null) return null;
  return (
    <span
      className={`turn-timer ${seconds <= 10 ? 'urgent' : ''}`}
      role="timer"
      aria-label="Time remaining"
    >
      {seconds > 0 ? `${seconds}s` : 'Time up — placing cards…'}
    </span>
  );
}
