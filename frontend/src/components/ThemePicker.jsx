import { useEffect, useState } from 'react';
import { readSaved, save } from '../lib/storage.js';

const themes = {
  forest: 'Forest',
  ocean: 'Ocean',
  plum: 'Plum',
  slate: 'Slate',
  sunset: 'Sunset',
  midnight: 'Midnight',
  casino: 'Casino',
};

export default function ThemePicker() {
  const [theme, setTheme] = useState(() => {
    const saved = readSaved('ofc.theme', 'forest');
    return Object.hasOwn(themes, saved) ? saved : 'forest';
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    save('ofc.theme', theme);
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute(
        'content',
        getComputedStyle(document.documentElement)
          .getPropertyValue('--felt')
          .trim(),
      );
  }, [theme]);

  return (
    <select
      className="theme-picker"
      aria-label="Colour theme"
      value={theme}
      onChange={(event) => setTheme(event.target.value)}
    >
      {Object.entries(themes).map(([value, label]) => (
        <option
          key={value}
          value={value}
        >
          {label}
        </option>
      ))}
    </select>
  );
}
