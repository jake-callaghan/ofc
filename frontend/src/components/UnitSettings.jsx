import { useState } from 'react';

export default function UnitSettings({
  value,
  onChange,
  enabled,
  onEnabledChange,
}) {
  const [scale, setScale] = useState(1);
  return (
    <fieldset className="unit-settings">
      <legend>Value per unit</legend>
      <div className="unit-options">
        <label>
          Amount
          <input
            type="number"
            required
            min="1"
            max={Math.floor(1_000_000_000 / scale)}
            step="1"
            value={value === '' ? '' : value / scale}
            onChange={(event) =>
              onChange(
                event.target.value === ''
                  ? ''
                  : Number(event.target.value) * scale,
              )
            }
          />
        </label>
        <label>
          Currency
          <select
            aria-label="Currency"
            value={scale}
            onChange={(event) => {
              const next = Number(event.target.value);
              if (value !== '') onChange((value / scale) * next);
              setScale(next);
            }}
          >
            <option value={1}>Pennies (p)</option>
            <option value={100}>Pounds (£)</option>
          </select>
        </label>
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
