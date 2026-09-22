import { useEffect, useRef, useState } from 'react';
import { api } from '../../lib/api.js';
import ErrorMessage from '../../components/ErrorMessage.jsx';

const reactions = ['😭', '🎉', '⏳', '🐟', '😂'];

export default function TableChat({ game, session, connection }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const messages = game.chat || [];
  const lastId = messages.at(-1)?.id;
  const [seen, setSeen] = useState(lastId);
  const input = useRef(null);
  const toggle = useRef(null);
  const bottom = useRef(null);
  const pending = useRef(null);
  const sending = useRef(false);
  const unread =
    !open && messages.some((message) => message.id !== seen) && lastId !== seen;

  useEffect(() => {
    if (open) {
      setSeen(lastId);
      bottom.current?.scrollIntoView({ block: 'nearest' });
    }
  }, [open, lastId]);

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);

  function close() {
    setOpen(false);
    toggle.current?.focus();
  }

  async function send(value, clearDraft = false) {
    if (!value.trim() || sending.current) return;
    if (!pending.current || pending.current.text !== value.trim()) {
      pending.current = { text: value.trim(), request_id: crypto.randomUUID() };
    }
    sending.current = true;
    setBusy(true);
    setError('');
    try {
      await api(`/games/${game.game_id}/chat`, session.token, pending.current);
      pending.current = null;
      if (clearDraft) setText('');
    } catch (err) {
      setError(err.message);
    } finally {
      sending.current = false;
      setBusy(false);
      input.current?.focus();
    }
  }

  return (
    <div className="table-chat">
      {open && (
        <section
          id="table-chat-panel"
          className="chat-panel"
          aria-label="Table chat"
          onKeyDown={(event) => {
            if (event.key === 'Escape') close();
          }}
        >
          <header className="chat-heading">
            <h2>Table chat</h2>
            <button
              type="button"
              aria-label="Hide chat"
              onClick={close}
            >
              ×
            </button>
          </header>
          <div
            className="chat-messages"
            role="log"
            aria-label="Messages"
            aria-live="polite"
            aria-relevant="additions"
          >
            {!messages.length && (
              <p className="hint">Say hello to the table.</p>
            )}
            {messages.map((message) => (
              <article
                className={`chat-message ${message.player === session.player_id ? 'own' : ''}`}
                key={message.id}
              >
                <div className="chat-byline">
                  <strong>{message.name}</strong>
                  <time
                    dateTime={new Date(message.created_at * 1000).toISOString()}
                  >
                    {new Date(message.created_at * 1000).toLocaleTimeString(
                      [],
                      { hour: '2-digit', minute: '2-digit' },
                    )}
                  </time>
                </div>
                <p
                  className={
                    reactions.includes(message.text)
                      ? 'chat-emoji-message'
                      : undefined
                  }
                >
                  {message.text}
                </p>
              </article>
            ))}
            <div ref={bottom} />
          </div>
          <form
            className="chat-compose"
            onSubmit={(event) => {
              event.preventDefault();
              send(text, true);
            }}
          >
            <ErrorMessage message={error} />
            <div
              className="chat-reactions"
              aria-label="Quick emoji messages"
            >
              {reactions.map((emoji) => (
                <button
                  type="button"
                  key={emoji}
                  aria-label={`Send ${emoji}`}
                  disabled={busy || connection !== 'live'}
                  onClick={() => send(emoji)}
                >
                  {emoji}
                </button>
              ))}
            </div>
            <label
              className="hint"
              htmlFor="chat-message"
            >
              Last 100 messages · table members only
            </label>
            <div>
              <input
                id="chat-message"
                ref={input}
                aria-label="Chat message"
                maxLength={1000}
                placeholder="Message the table…"
                autoComplete="off"
                value={text}
                disabled={busy}
                onChange={(event) => setText(event.target.value)}
              />
              <button
                type="submit"
                className="secondary"
                disabled={busy || connection !== 'live' || !text.trim()}
              >
                Send
              </button>
            </div>
            {connection !== 'live' && (
              <p className="hint">Reconnecting to chat…</p>
            )}
          </form>
        </section>
      )}
      <button
        type="button"
        ref={toggle}
        className={`chat-toggle ${unread ? 'has-unread' : ''}`}
        aria-label={open ? 'Close table chat' : 'Open table chat'}
        aria-expanded={open}
        aria-controls="table-chat-panel"
        onClick={() => (open ? close() : setOpen(true))}
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          aria-hidden="true"
        >
          <path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-6 4V6a2 2 0 0 1 2-2Z" />
          <path d="M7 9h10M7 13h7" />
        </svg>
        {unread && (
          <span
            className="chat-unread"
            aria-label="Unread messages"
          />
        )}
      </button>
    </div>
  );
}
