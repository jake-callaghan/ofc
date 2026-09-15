import { useEffect, useState } from 'react';

export default function InstallApp() {
  const [prompt, setPrompt] = useState(null);
  const [installed, setInstalled] = useState(
    () =>
      window.matchMedia('(display-mode: standalone)').matches ||
      navigator.standalone,
  );
  const [help, setHelp] = useState(false);

  useEffect(() => {
    const displayMode = window.matchMedia('(display-mode: standalone)');
    const ready = (event) => {
      event.preventDefault();
      setPrompt(event);
    };
    const complete = () => {
      setInstalled(true);
      setPrompt(null);
      setHelp(false);
    };
    const changed = () =>
      setInstalled(displayMode.matches || navigator.standalone);
    window.addEventListener('beforeinstallprompt', ready);
    window.addEventListener('appinstalled', complete);
    displayMode.addEventListener('change', changed);
    return () => {
      window.removeEventListener('beforeinstallprompt', ready);
      window.removeEventListener('appinstalled', complete);
      displayMode.removeEventListener('change', changed);
    };
  }, []);

  async function install() {
    if (!prompt) {
      setHelp(!help);
      return;
    }
    try {
      await prompt.prompt();
      await prompt.userChoice;
    } catch {
      setHelp(true);
    } finally {
      // browser install prompts can only be used once.
      setPrompt(null);
    }
  }

  if (installed) return null;

  return (
    <div className="install-app">
      <button
        className="text-button"
        onClick={install}
        aria-expanded={help}
        aria-controls="install-help"
      >
        Add to home screen
      </button>
      {help && (
        <div
          id="install-help"
          className="install-help"
        >
          <p>
            iPhone / iPad: open in Safari, tap Share, then Add to Home Screen.
          </p>
          <p>
            Android: open the browser menu and choose Install app or Add to Home
            screen.
          </p>
          <button
            className="text-button"
            onClick={() => setHelp(false)}
          >
            Close
          </button>
        </div>
      )}
    </div>
  );
}
