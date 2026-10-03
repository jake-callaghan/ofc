import { useEffect, useRef } from 'react';
import Leaderboard from './Leaderboard.jsx';

export default function LeaderboardModal({ session, onClose }) {
  const dialog = useRef(null);
  useEffect(() => {
    const element = dialog.current;
    const trigger = document.activeElement;
    const overflow = document.body.style.overflow;
    element.showModal();
    document.body.style.overflow = 'hidden';
    return () => {
      element.close();
      document.body.style.overflow = overflow;
      if (trigger?.isConnected) trigger.focus();
    };
  }, []);

  return (
    <dialog
      ref={dialog}
      className="leaderboard-modal"
      aria-labelledby="leaderboard-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target !== event.currentTarget) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < bounds.left ||
          event.clientX > bounds.right ||
          event.clientY < bounds.top ||
          event.clientY > bounds.bottom
        )
          onClose();
      }}
    >
      <div className="modal-heading">
        <h2 id="leaderboard-title">Global leaderboard</h2>
        <button
          className="secondary modal-close"
          onClick={onClose}
          aria-label="Close leaderboard"
          autoFocus
        >
          ×
        </button>
      </div>
      <Leaderboard session={session} />
    </dialog>
  );
}
