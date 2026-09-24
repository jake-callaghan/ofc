import { useEffect, useState } from 'react';
import { readSaved, save } from './lib/storage.js';
import { route } from './lib/navigation.js';
import Header from './components/Header.jsx';
import Footer from './components/Footer.jsx';
import AmbientBackground from './components/AmbientBackground.jsx';
import Welcome from './features/player/Welcome.jsx';
import GuestWelcome from './features/player/GuestWelcome.jsx';
import Account from './features/player/Account.jsx';
import { api } from './lib/api.js';
import ErrorMessage from './components/ErrorMessage.jsx';
import Lobby from './features/lobby/Lobby.jsx';
import Table from './features/table/Table.jsx';
export default function App() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState(null);
  const [error, setError] = useState('');
  const [accountOpen, setAccountOpen] = useState(false);
  const [notice, setNotice] = useState('');
  useEffect(() => {
    let active = true;
    const params = new URLSearchParams(location.search);
    if (params.has('auth_error'))
      setError('The sign-in link failed or expired. Please start again.');
    if (params.has('auth')) {
      const target = sessionStorage.getItem('ofc.login-return');
      sessionStorage.removeItem('ofc.login-return');
      if (target?.startsWith('#')) location.hash = target;
    }
    if (params.has('auth') || params.has('auth_error'))
      history.replaceState(null, '', location.pathname + location.hash);
    api('/auth/config')
      .then(async (value) => {
        if (!active) return;
        setConfig(value);
        if (value.legacy && !value.enabled) {
          setSession(readSaved('ofc.player', null));
        } else {
          localStorage.removeItem('ofc.player');
          if (value.enabled) {
            try {
              const own = await api('/auth/session');
              if (active) setSession(own);
            } catch (e) {
              if (e.status !== 401 && active) setError(e.message);
            }
          }
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    const expired = () => {
      setSession(null);
      setAccountOpen(false);
      setError('Your session expired. Please sign in again.');
    };
    window.addEventListener('ofc-session-expired', expired);
    return () => {
      active = false;
      window.removeEventListener('ofc-session-expired', expired);
    };
  }, []);
  const [page, setPage] = useState(route);
  useEffect(() => {
    const update = () => setPage(route());
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  function login(data) {
    if (data.token) save('ofc.player', data);
    setError('');
    setNotice('');
    setSession(data);
  }
  async function logout() {
    try {
      await api('/auth/logout', null, {});
      setSession(null);
      setAccountOpen(false);
      home();
    } catch (e) {
      setError(e.message);
    }
  }
  function passwordSaved(message) {
    setSession(null);
    setAccountOpen(false);
    setNotice(message);
  }
  function home() {
    location.hash = '';
    setPage({ id: null, join: null });
  }
  function openGame(id, name) {
    const key = `ofc.tables.${session.player_id}`;
    save(key, [{ id, name }, ...readSaved(key, []).filter((t) => t.id !== id)]);
    location.hash = `game=${encodeURIComponent(id)}`;
  }
  return (
    <>
      <AmbientBackground atTable={!!page.id} />
      <Header
        session={session}
        home={home}
        account={() => setAccountOpen(true)}
        logout={logout}
      />
      <ErrorMessage message={error} />
      {loading && (
        <main className="panel">
          <p>Checking your session…</p>
        </main>
      )}
      {!loading &&
        !session &&
        (config?.legacy && !config.enabled ? (
          <GuestWelcome onSession={login} />
        ) : (
          <Welcome
            onSession={login}
            enabled={config?.enabled}
            notice={notice}
          />
        ))}
      {session && (accountOpen || session.recovery) && (
        <Account
          session={session}
          onClose={() => setAccountOpen(false)}
          onPasswordSaved={passwordSaved}
        />
      )}

      {session && !session.recovery && !accountOpen && page.id && (
        <Table
          key={`${session.player_id}:${page.id}`}
          id={page.id}
          session={session}
          home={home}
        />
      )}

      {session && !session.recovery && !accountOpen && !page.id && (
        <Lobby
          key={page.join || 'lobby'}
          session={session}
          openGame={openGame}
          pendingJoin={page.join}
        />
      )}
      <Footer />
    </>
  );
}
