// adapted from magic ui's shimmer and interactive hover buttons (mit).
// source links and licence are in frontend/THIRD_PARTY_NOTICES.md.
export default function ActionButton({ children, className = '', ...props }) {
  return (
    <button
      className={`primary shimmer-button ${className}`}
      {...props}
    >
      <span
        className="shimmer-spark"
        aria-hidden="true"
      />
      <span
        className="shimmer-backdrop"
        aria-hidden="true"
      />
      <span className="shimmer-label">{children}</span>
    </button>
  );
}

export function HoverButton({ children, className = '', ...props }) {
  return (
    <button
      className={`hover-button ${className}`}
      {...props}
    >
      <span
        className="hover-button-dot"
        aria-hidden="true"
      />
      <span className="hover-button-label">{children}</span>
      <svg
        className="hover-button-arrow"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path d="M5 12h14m-6-6 6 6-6 6" />
      </svg>
    </button>
  );
}
