import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../lib/api.js';

export function useGame(id, token) {
  const [game, setGame] = useState(null);
  const [connection, setConnection] = useState('connecting');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const current = useRef(null);
  const pending = useRef(null);
  const accept = useCallback((state, serverTime) => {
    if (current.current && state.version < current.current.version) return;
    const clockOffset =
      typeof serverTime === 'number'
        ? serverTime * 1000 - Date.now()
        : current.current?.clockOffset || 0;
    const snapshot = { ...state, clockOffset };
    current.current = snapshot;
    setGame(snapshot);
  }, []);

  useEffect(() => {
    let stopped = false,
      socket,
      timer,
      attempts = 0;
    const controller = new AbortController();
    current.current = null;
    setGame(null);
    function connect() {
      if (stopped) return;
      setConnection('connecting');
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      socket = new WebSocket(
        `${protocol}//${location.host}/api/games/${id}/events`,
      );
      socket.onopen = () => socket.send(JSON.stringify({ token }));
      socket.onmessage = (event) => {
        if (stopped) return;
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'snapshot') {
            accept(message.state, message.server_time);
            attempts = 0;
            setConnection('live');
          }
        } catch {
          setError('An update could not be read. Reconnecting may help.');
        }
      };
      socket.onclose = (event) => {
        if (stopped) return;
        setConnection('offline');
        if (event.code === 1008) {
          setError(
            'This identity cannot access the table. Check your invitation or player token.',
          );
          return;
        }
        timer = setTimeout(connect, Math.min(1000 * 2 ** attempts++, 15000));
      };
    }
    api(`/games/${id}`, token, undefined, controller.signal)
      .then((state) => {
        if (!stopped) accept(state);
      })
      .catch((e) => {
        if (!stopped) setError(e.message);
      });
    connect();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
      socket?.close();
    };
  }, [id, token, accept]);

  async function command(value) {
    if (busy || !current.current) return false;
    const serialized = JSON.stringify(value);
    // retain the request id after a transport failure, so a retry cannot replay a move.
    if (!pending.current || pending.current.serialized !== serialized) {
      pending.current = {
        serialized,
        body: {
          request_id: crypto.randomUUID(),
          version: current.current.version,
          command: value,
        },
      };
    }
    setBusy(true);
    setError('');
    try {
      const result = await api(
        `/games/${id}/commands`,
        token,
        pending.current.body,
      );
      if (result.state) accept(result.state);
      pending.current = null;
      return true;
    } catch (e) {
      if (e.status) pending.current = null;
      if (e.status === 409) {
        try {
          accept(await api(`/games/${id}`, token));
        } catch {
          /* the websocket will also attempt recovery. */
        }
        setError(
          'The table changed. Review the latest state and submit again.',
        );
      } else setError(e.message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  return { game, connection, error, setError, busy, command };
}
