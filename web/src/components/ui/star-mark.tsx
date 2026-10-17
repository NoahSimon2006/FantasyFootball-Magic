/**
 * The four-point star from the logo. Decorative everywhere it appears (the words beside it
 * carry the meaning), so it is hidden from assistive tech. Colour comes from `currentColor`.
 */
export function StarMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <path
        fill="currentColor"
        d="M12 1.5c.5 5.6 4.9 10 10.5 10.5-5.6.5-10 4.9-10.5 10.5-.5-5.6-4.9-10-10.5-10.5C7.1 11.5 11.5 7.1 12 1.5Z"
      />
    </svg>
  );
}
