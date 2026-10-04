import type { SVGProps } from "react";

// A medical cross built from five rounded squares, like nodes on a grid; the
// center square carries the primary accent.
export function Logo({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className} {...props}>
      <g fill="currentColor">
        <rect x="8.8" y="1.2" width="6.4" height="6.4" rx="1.8" />
        <rect x="1.2" y="8.8" width="6.4" height="6.4" rx="1.8" />
        <rect x="16.4" y="8.8" width="6.4" height="6.4" rx="1.8" />
        <rect x="8.8" y="16.4" width="6.4" height="6.4" rx="1.8" />
      </g>
      <rect
        className="brand-mark-accent"
        x="8.8"
        y="8.8"
        width="6.4"
        height="6.4"
        rx="1.8"
      />
    </svg>
  );
}
