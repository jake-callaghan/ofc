import { useEffect, useRef } from 'react';
import InstallApp from './InstallApp.jsx';
import SuitColours from './SuitColours.jsx';
import ThemePicker from './ThemePicker.jsx';

export default function Settings() {
  const menu = useRef(null);

  useEffect(() => {
    const outside = (event) => {
      if (!menu.current.contains(event.target)) menu.current.open = false;
    };
    const escape = (event) => {
      if (event.key === 'Escape' && menu.current.open) {
        menu.current.open = false;
        menu.current.querySelector('summary').focus();
      }
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  }, []);

  return (
    <details
      className="settings"
      ref={menu}
    >
      <summary>Settings</summary>
      <div className="settings-panel">
        <div className="settings-row">
          <span>Theme</span>
          <ThemePicker />
        </div>
        <SuitColours />
        <InstallApp />
      </div>
    </details>
  );
}
