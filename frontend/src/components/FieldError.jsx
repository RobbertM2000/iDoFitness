export default function FieldError({ children }) {
  if (!children) return null;
  return (
    <p style={{ color: "var(--danger)", fontSize: 13, margin: "4px 0 0" }}>
      {children}
    </p>
  );
}
