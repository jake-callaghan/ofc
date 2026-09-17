import { useEffect, useState } from 'react';
import { readSaved, save } from '../lib/storage.js';

export default function BackgroundMotion() {
  const [motion, setMotion] = useState(
    () => readSaved('ofc.backgroundMotion', true) === true,
  );

  useEffect(() => {
    document.documentElement.dataset.backgroundMotion = String(motion);
    save('ofc.backgroundMotion', motion);
  }, [motion]);

  return (
    <button
      className="suit-switch background-motion"
      role="switch"
      aria-checked={motion}
      onClick={() => setMotion(!motion)}
    >
      <span>Background motion</span>
      <span
        className="switch-track"
        aria-hidden="true"
      >
        <span />
      </span>
    </button>
  );
}
