import { useEffect, useState } from 'react';
import { readSaved, save } from './lib/storage.js';
import { route } from './lib/navigation.js';
import Header from './components/Header.jsx';
import Footer from './components/Footer.jsx';
import AmbientBackground from './components/AmbientBackground.jsx';
import Welcome from './features/player/Welcome.jsx';
import Lobby from './features/lobby/Lobby.jsx';
import Table from './features/table/Table.jsx';
export default function App() {
  const [session, setSession] = useState(() => readSaved('ofc.player', null));
  const [page, setPage] = useState(route);
  useEffect(() => {
    const update = () => setPage(route());
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  function login(data) {
    save('ofc.player', data);
    setSession(data);
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
      />
      {!session && <Welcome onSession={login} />}

      {session && page.id && (
        <Table
          key={`${session.player_id}:${page.id}`}
          id={page.id}
          session={session}
          home={home}
        />
      )}

      {session && !page.id && (
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
