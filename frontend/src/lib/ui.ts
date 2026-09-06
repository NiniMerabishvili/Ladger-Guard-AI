export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export const surface =
  "rounded-2xl border border-line bg-elevated shadow-[0_18px_40px_rgba(0,0,0,0.28)]";

export const btn =
  "inline-flex items-center rounded-[10px] border border-line bg-elevated px-3.5 py-2 text-ink-text hover:border-[#3d4d63] disabled:cursor-not-allowed disabled:opacity-50";

export const btnPrimary =
  "inline-flex items-center rounded-[10px] border border-transparent bg-mint px-3.5 py-2 font-semibold text-mint-ink disabled:cursor-not-allowed disabled:opacity-50";

export const btnDanger =
  "inline-flex items-center rounded-[10px] border border-low/35 bg-low/12 px-3.5 py-2 text-[#ffc2bd] disabled:cursor-not-allowed disabled:opacity-50";

export const badgeBase =
  "inline-flex items-center rounded-full px-2 py-0.5 text-xs tracking-wide";

export const badges = {
  high: `${badgeBase} bg-mint/14 text-mint`,
  medium: `${badgeBase} bg-medium/12 text-medium`,
  low: `${badgeBase} bg-low/12 text-[#ffb3ad]`,
  bank: `${badgeBase} bg-bank/12 text-bank`,
  ledger: `${badgeBase} bg-ledger/12 text-ledger`,
  neutral: `${badgeBase} bg-[#1b2430] text-muted`,
} as const;

export const panel = "rounded-2xl border border-dashed border-line px-9 py-9 text-muted";
export const panelError = "rounded-2xl border border-dashed border-low/40 px-9 py-9 text-[#ffc2bd]";
export const panelSuccess =
  "rounded-2xl border border-dashed border-mint/40 bg-mint/8 px-9 py-9 text-mint";
export const pageHeader = "mb-7 flex items-end justify-between gap-4";
export const pageTitle = "mb-1.5 text-[1.7rem] font-semibold tracking-tight";
export const pageLead = "m-0 max-w-xl text-muted";
