export default function EmptyTable({ watching = false, visibility }) {
  return (
    <section className="empty-table">
      <h2>{watching ? 'Watching the table' : 'Ready to play'}</h2>
      <p>
        {watching
          ? visibility === 'open'
            ? 'Join the table to play, or wait here to watch the next hand.'
            : 'You can watch here. An invitation is required to join this private table.'
          : 'Invite a friend or add a CPU, then deal.'}
      </p>
    </section>
  );
}
