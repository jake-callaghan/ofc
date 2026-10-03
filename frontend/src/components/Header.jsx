import Settings from './Settings.jsx';

const brand = (
  <>
    <span className="brand-mark">♠</span>
    <span>Open Face Chinese Poker</span>
  </>
);
export default function Header({
  session,
  home,
  account,
  logout,
  leaderboard,
}) {
  return (
    <header className="header">
      <button
        className="brand"
        onClick={home}
      >
        {brand}
      </button>
      <div className="header-right">
        {session && (
          <span className="identity">
            <span className="avatar">
              {session.name.slice(0, 1).toUpperCase()}
            </span>
            <span className="identity-name">{session.name}</span>
          </span>
        )}
        <Settings
          session={session}
          home={home}
          account={account}
          logout={logout}
          leaderboard={leaderboard}
        />
      </div>
    </header>
  );
}
