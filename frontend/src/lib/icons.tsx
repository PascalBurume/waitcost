// Small inline icon set — stroke-based, inherits currentColor so it themes for
// free. Keeps the bundle dependency-light and offline.
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement> & { size?: number };
const base = (size = 16): SVGProps<SVGSVGElement> => ({
  width: size, height: size, viewBox: "0 0 24 24", fill: "none",
  stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
  "aria-hidden": true,
});

export const Icon = {
  Ask: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="M12 3a9 9 0 0 1 0 18c-1.5 0-2.9-.4-4.2-1L3 21l1.1-4.5A9 9 0 0 1 12 3Z" /><path d="M9 10h6M9 14h4" /></svg>),
  Explore: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="M4 19V5M4 19h16" /><path d="M8 16l3-4 3 2 4-7" /></svg>),
  Visualize: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M8 14v3M12 10v7M16 7v10" /></svg>),
  Brain: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="M9 3a3 3 0 0 0-3 3 3 3 0 0 0-1 5 3 3 0 0 0 1 5 3 3 0 0 0 3 3 2.5 2.5 0 0 0 3 0 3 3 0 0 0 3-3 3 3 0 0 0 1-5 3 3 0 0 0-1-5 3 3 0 0 0-3-3 2.5 2.5 0 0 0-3 0Z" /><path d="M12 6v12" /></svg>),
  Equity: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="M12 3v18M5 7h14M7 7l-3 6a3 3 0 0 0 6 0L7 7Zm10 0-3 6a3 3 0 0 0 6 0l-3-6Z" /></svg>),
  Shield: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="M12 3l7 3v5c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6l7-3Z" /><path d="M9.5 12l2 2 3.5-4" /></svg>),
  Map: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Z" /><path d="M9 4v14M15 6v14" /></svg>),
  Send: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="M5 12h14M13 6l6 6-6 6" /></svg>),
  Search: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>),
  Chevron: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="m6 9 6 6 6-6" /></svg>),
  ChevronRight: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="m9 6 6 6-6 6" /></svg>),
  Check: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="M20 6 9 17l-5-5" /></svg>),
  Info: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>),
  Lock: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></svg>),
  Spinner: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="M12 3a9 9 0 1 0 9 9" /></svg>),
  Sun: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>),
  Moon: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" /></svg>),
  Slash: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><circle cx="12" cy="12" r="9" /><path d="m5.6 5.6 12.8 12.8" /></svg>),
  Doc: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" /><path d="M14 3v5h5M9 13h6M9 17h6" /></svg>),
  Database: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></svg>),
  Scale: ({ size, ...p }: P) => (<svg {...base(size)} {...p}><path d="M3 7h18M12 3v4M6 21h12M9 21V11M15 21V11" /></svg>),
};

export type IconName = keyof typeof Icon;
