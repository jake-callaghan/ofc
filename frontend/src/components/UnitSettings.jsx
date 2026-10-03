import { unitValue } from '../lib/money.js';

export default function UnitSettings({
  value,
  onChange,
  enabled,
  onEnabledChange,
}) {
  return (
    <fieldset className="unit-settings">
      <legend>Value per unit</legend>
      <div className="unit-options">
        {[10, 50, 100].map((pence) => (
          <button
            key={pence}
            type="button"
            className={value === pence ? 'primary' : 'secondary'}
            aria-pressed={value === pence}
            onClick={() => onChange(pence)}
          >
            {unitValue(pence)}
          </button>
        ))}
      </div>
      <label className="check">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => onEnabledChange(event.target.checked)}
        />
        Count towards the global leaderboard
      </label>
      <p className="hint">Only hands played entirely by humans count.</p>
    </fieldset>
  );
}
