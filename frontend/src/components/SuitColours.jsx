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
      className="suit-toggle secondary"
      aria-pressed={fourColours}
      onClick={() => setFourColours(!fourColours)}
    >
      Four-colour suits
    </button>
  );
}
