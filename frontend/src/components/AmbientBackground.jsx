import { useEffect, useState } from 'react';

export default function AmbientBackground({ atTable }) {
  const [hidden, setHidden] = useState(() => document.hidden);

  useEffect(() => {
    const changed = () => setHidden(document.hidden);
    document.addEventListener('visibilitychange', changed);
    return () => document.removeEventListener('visibilitychange', changed);
  }, []);

  return (
    <div
      className={`ambient-background ${atTable ? 'at-table' : ''}`}
      data-paused={hidden}
      aria-hidden="true"
    >
      <div className="ambient-layer ambient-one" />
      <div className="ambient-layer ambient-two" />
      <div className="ambient-layer ambient-three" />
      <div className="ambient-dots" />
    </div>
  );
}
