import Settings from './Settings.jsx';

const brand = (
  <>
    <span className="brand-mark">♠</span>
    <span>Open Face Chinese Poker</span>
  </>
);
export default function Header({ session, home, account, logout }) {
  return (
    <header className="header">
      <button
        className="brand"
        onClick={home}
      >
        {brand}
      </button>
      <div className="header-right">
        <Settings session={session} />
        {session && !session.token && (
          <>
            <button
              className="text-button"
              onClick={account}
            >
              Account
            </button>
            <button
              className="text-button"
              onClick={logout}
            >
              Sign out
            </button>
          </>
        )}
        {session && (
          <span className="identity">
            <span className="avatar">
              {session.name.slice(0, 1).toUpperCase()}
            </span>
            {session.name}
          </span>
        )}
      </div>
    </header>
  );
}
