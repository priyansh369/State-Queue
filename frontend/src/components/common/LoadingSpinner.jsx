export default function LoadingSpinner({ label = "Loading..." }) {
  return (
    <div className="loading-inline" role="status" aria-live="polite">
      <span className="spinner" />
      <span>{label}</span>
    </div>
  );
}
