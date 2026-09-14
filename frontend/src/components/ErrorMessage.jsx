export default function ErrorMessage({ message }) {
  return message ? (
    <div
      className="error"
      role="alert"
    >
      {message}
    </div>
  ) : null;
}
