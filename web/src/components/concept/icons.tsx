export function TriangleMark({ className = "mt-1.5 h-3 w-3 shrink-0 text-terracotta" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 12 12" aria-hidden="true">
      <path fill="currentColor" d="M6 1.1 11.2 11H.8z" />
    </svg>
  );
}

export function PinMark({ className = "mt-0.5 h-4 w-4 shrink-0 text-terracotta" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 2.5c-3.7 0-6.7 3-6.7 6.7 0 4.7 5.4 10.6 6.2 11.4a.7.7 0 0 0 1 0c.8-.8 6.2-6.7 6.2-11.4 0-3.7-3-6.7-6.7-6.7Zm0 9.2a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5Z"
      />
    </svg>
  );
}
