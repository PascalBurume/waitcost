// Formatting helpers. The engine speaks in $M (millions); these render compact,
// honest figures. Never invent — these only format numbers the API returned.

/** Format a value given in MILLIONS of dollars → "$345.6M" / "$1.07B". */
export function fmtMusd(musd: number, dp = 1): string {
  const a = Math.abs(musd);
  if (a >= 1000) return `$${(musd / 1000).toFixed(a >= 10000 ? 1 : 2)}B`;
  return `$${musd.toFixed(dp)}M`;
}

/** Format raw dollars → compact "$866K" / "$9.5M" / "$1.2B". */
export function fmtUsd(v: number): string {
  const a = Math.abs(v);
  if (a >= 1e9) return `$${(v / 1e9).toFixed(a >= 1e10 ? 0 : 1)}B`;
  if (a >= 1e6) return `$${(v / 1e6).toFixed(a >= 1e8 ? 0 : 1)}M`;
  if (a >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${Math.round(v)}`;
}

/** Thousands-separated integer. */
export function fmtNum(v: number): string {
  return Math.round(v).toLocaleString("en-US");
}

export function fmtPct(v: number, dp = 1): string {
  return `${v.toFixed(dp)}%`;
}

/** A musd range "$282.2M – $412.6M". */
export function fmtRange(lo: number, hi: number): string {
  return `${fmtMusd(lo)} – ${fmtMusd(hi)}`;
}

/** Render the API's lightweight markdown (only **bold** + em-dashes) to React-safe HTML. */
export function mdInline(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/(^|[\s(])\*(?!\s)(.+?)(?<!\s)\*/g, "$1<em>$2</em>");   // *italic* (after ** so it doesn't eat bold)
}
