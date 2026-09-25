import { useEffect, useState } from 'react';
import { api } from '../../lib/api.js';
import ErrorMessage from '../../components/ErrorMessage.jsx';

export default function ActiveTables({ session, openGame }) {
  const [tables, setTables] = useState(null);
  const [error, setError] = useState('');
  const [joining, setJoining] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    async function refresh() {
      try {
        if (!document.hidden) {
          const result = await api(
            '/games',
            session.token,
            undefined,
            controller.signal,
          );
          if (!controller.signal.aborted) {
            setTables(result);
            setError('');
          }
        }
      } catch (e) {
        if (!controller.signal.aborted) setError(e.message);
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 10000);
      }
    }
    refresh();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [session.token]);

  async function join(table) {
    setJoining(table.id);
    setError('');
    try {
      const result = await api(`/games/${table.id}/join`, session.token, {
        request_id: crypto.randomUUID(),
      });
      openGame(table.id, result.state.name);
    } catch (e) {
      setError(e.message);
    } finally {
      setJoining(null);
    }
  }

  return (
    <section className="panel active-tables">
      <h2>Active tables</h2>
      <p className="hint">
        Watch any table. Join an open table, or use an invite for a private
        table.
      </p>
      <ErrorMessage message={error} />
      {!tables ? (
        <p>Loading tables…</p>
      ) : !tables.length ? (
        <p>No active tables yet. Create one below.</p>
      ) : (
        <div className="lobby-table-scroll">
          <table className="lobby-table">
            <thead>
              <tr>
                <th>Table</th>
                <th>Players</th>
                <th>Location</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tables.map((table) => (
                <tr key={table.id}>
                  <td>
                    <strong>{table.name}</strong>
                    <small>
                      {table.variant} ·{' '}
                      {table.visibility === 'open'
                        ? 'Open'
                        : 'Private · invite-only'}
                      {table.is_member ? ' · Your table' : ''}
                    </small>
                  </td>
                  <td>{table.member_count}</td>
                  <td className="table-location">🇬🇧 London</td>
                  <td>
                    {table.phase === 'playing'
                      ? `Playing hand ${table.hand_number}`
                      : 'Between hands'}
                  </td>
                  <td>
                    <div className="lobby-table-actions">
                      <button
                        className="secondary"
                        onClick={() => openGame(table.id, table.name)}
                        aria-label={`View ${table.name}`}
                      >
                        View
                      </button>
                      {!table.is_member && table.visibility === 'open' && (
                        <button
                          className="primary"
                          disabled={joining !== null}
                          onClick={() => join(table)}
                          aria-label={`Join ${table.name}`}
                        >
                          {joining === table.id ? 'Joining…' : 'Join'}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
