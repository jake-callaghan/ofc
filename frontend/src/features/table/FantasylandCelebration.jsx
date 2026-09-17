export default function FantasylandCelebration() {
  return (
    <div
      className="fantasyland-celebration"
      role="status"
    >
      <span
        className="fantasyland-confetti"
        aria-hidden="true"
      >
        {Array.from({ length: 24 }, (_, index) => (
          <i
            key={index}
            style={{
              '--x': `${(index * 37) % 100}%`,
              '--delay': `${(index % 6) * 0.12}s`,
              '--spin': `${index % 2 ? 260 : -260}deg`,
              '--confetti-colour': [
                'var(--gold)',
                'var(--green)',
                '#e885ba',
                '#7bbcf5',
              ][index % 4],
            }}
          />
        ))}
      </span>
      <strong>Fantasyland!</strong>
    </div>
  );
}
