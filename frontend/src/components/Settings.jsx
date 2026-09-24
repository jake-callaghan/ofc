import { useEffect, useRef } from 'react';
import InstallApp from './InstallApp.jsx';
import SuitColours from './SuitColours.jsx';
import ThemePicker from './ThemePicker.jsx';
import BackgroundMotion from './BackgroundMotion.jsx';

export default function Settings({ session }) {
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

  function backup() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(session)], { type: 'application/json' }),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = 'open-face-player-key.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <details
      className="settings"
      ref={menu}
    >
      <summary>Settings</summary>
      <div className="settings-panel">
        <div className="settings-heading">Preferences</div>
        <div className="settings-row">
          <span>Theme</span>
          <ThemePicker />
        </div>
        <BackgroundMotion />
        <SuitColours />
        <InstallApp />
        {session?.token && (
          <button
            className="text-button player-key-download"
            onClick={backup}
          >
            Download player key
          </button>
        )}
      </div>
    </details>
  );
}
