import { useEffect, useState } from 'react';
import { readSaved, save } from '../lib/storage.js';

const themes = {
  ocean: { label: 'Ocean', background: 'waves' },
  slate: { label: 'Slate', background: 'shapes' },
  midnight: { label: 'Midnight', background: 'dots' },
  casino: { label: 'Casino', background: 'shapes' },
};

export default function ThemePicker() {
  const [theme, setTheme] = useState(() => {
    const saved = readSaved('ofc.theme', 'casino');
    return Object.hasOwn(themes, saved) ? saved : 'casino';
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.background = themes[theme].background;
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
      {Object.entries(themes).map(([value, { label }]) => (
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
