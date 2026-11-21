import { useEffect, useState } from 'react';
import { useEffects } from './Effects.jsx';
import { units } from '../lib/game.js';

export default function AnimatedUnits({ value, delay = 0 }) {
  const { enabled } = useEffects();
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    if (!enabled) return;
    setDisplay(0);
    let frame;
    const timer = setTimeout(() => {
      const start = performance.now();
      const tick = (now) => {
        const progress = Math.min(1, (now - start) / 650);
        setDisplay(Math.round(value * (1 - (1 - progress) ** 3)));
        if (progress < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    }, delay);
    return () => {
      clearTimeout(timer);
      cancelAnimationFrame(frame);
    };
  }, [value, delay, enabled]);
  return (
    <span aria-label={units(value)}>
      <span aria-hidden="true">{units(enabled ? display : value)}</span>
    </span>
  );
}
