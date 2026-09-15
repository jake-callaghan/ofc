import { useEffect, useState } from 'react';

export default function useTurnTimer(game) {
  const deadline = game.hand?.deadline;
  const [now, setNow] = useState(Date.now);

  useEffect(() => {
    setNow(Date.now());
    if (deadline == null) return;
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [deadline]);

  if (deadline == null) return null;
  return Math.max(
    0,
    Math.ceil((deadline * 1000 - now - (game.clockOffset || 0)) / 1000),
  );
}
