import { createContext, useContext, useEffect, useState } from 'react';
import { readSaved, save } from '../lib/storage.js';

const EffectsContext = createContext({ enabled: false, preference: true });

export function EffectsProvider({ children }) {
  const [preference, setPreference] = useState(
    () => readSaved('ofc.effects', true) === true,
  );
  const [reduced, setReduced] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(media.matches);
    media.addEventListener('change', update);
    update();
    return () => media.removeEventListener('change', update);
  }, []);
  const enabled = preference && !reduced;
  useEffect(() => {
    document.documentElement.dataset.effects = String(enabled);
    save('ofc.effects', preference);
  }, [enabled, preference]);
  return (
    <EffectsContext.Provider
      value={{ enabled, preference, setPreference, reduced }}
    >
      {children}
    </EffectsContext.Provider>
  );
}

export const useEffects = () => useContext(EffectsContext);

export default function EffectsToggle() {
  const { preference, setPreference, reduced } = useEffects();
  return (
    <div>
      <button
        className="suit-switch"
        role="switch"
        aria-checked={preference}
        onClick={() => setPreference(!preference)}
      >
        <span>Effects</span>
        <span
          className="switch-track"
          aria-hidden="true"
        >
          <span />
        </span>
      </button>
      {reduced && (
        <small className="effects-note">
          Animations paused by your reduced-motion preference.
        </small>
      )}
    </div>
  );
}
