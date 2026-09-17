import { useEffect, useState } from 'react';
import { readSaved, save } from '../lib/storage.js';

export default function SuitColours() {
  const [fourColours, setFourColours] = useState(
    () => readSaved('ofc.fourColours', true) === true,
  );

  useEffect(() => {
    document.documentElement.dataset.suitColours = fourColours ? 'four' : 'two';
    save('ofc.fourColours', fourColours);
  }, [fourColours]);

  return (
    <button
      className="suit-switch"
      role="switch"
      aria-checked={fourColours}
      onClick={() => setFourColours(!fourColours)}
    >
      <span>Four-colour suits</span>
      <span
        className="switch-track"
        aria-hidden="true"
      >
        <span />
      </span>
    </button>
  );
}
