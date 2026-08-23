// GENERATED from schemas/design/tokens.json. Do not edit.
// Regenerate with: uv run python -m scripts.generate_design_tokens

export const TOKENS_VERSION = 1;

export const ColorPalette: Readonly<Record<string, string>> = {
  "bg": "#1e1e1e",
  "card": "#252526",
  "fg": "#e6e6e6",
  "muted": "#b0b0b0",
  "border": "rgba(200,200,200,0.28)",
  "accent": "#1177bb",
  "accentBright": "#6cb6ff",
  "accentFg": "#ffffff",
  "focus": "#4fc1ff",
  "ok": "#3fb950",
  "warn": "#e3b341",
  "err": "#f85149",
  "borderHover": "rgba(200,200,200,0.45)",
  "hoverWash": "rgba(255,255,255,0.04)",
  "okBorder": "rgba(63,185,80,0.4)",
  "okWash": "rgba(63,185,80,0.1)",
  "warnBorder": "rgba(227,179,65,0.4)",
  "warnWash": "rgba(227,179,65,0.08)",
  "errBorder": "rgba(248,81,73,0.4)",
  "errWash": "rgba(248,81,73,0.08)",
  "insetWash": "rgba(0,0,0,0.15)"
};

export const SemanticColors: Readonly<Record<string, string>> = {
  "--surface-base": "--bg",
  "--surface-card": "--card",
  "--text-primary": "--fg",
  "--text-muted": "--muted",
  "--border-default": "--border",
  "--accent-primary": "--accent",
  "--accent-bright-text": "--accent-bright",
  "--border-hover-line": "--border-hover",
  "--hover-wash-bg": "--hover-wash",
  "--ok-border-line": "--ok-border",
  "--ok-wash-bg": "--ok-wash",
  "--warn-border-line": "--warn-border",
  "--warn-wash-bg": "--warn-wash",
  "--err-border-line": "--err-border",
  "--err-wash-bg": "--err-wash",
  "--inset-wash-bg": "--inset-wash",
  "--accent-on-accent": "--accent-fg",
  "--status-ok": "--ok",
  "--status-warn": "--warn",
  "--status-err": "--err",
  "--focus-ring": "--focus"
};

export const SpacingScalePx: Readonly<Record<string, number>> = {
  "space0": 0,
  "space1": 4,
  "space2": 8,
  "space3": 12,
  "space4": 16,
  "space5": 20,
  "space6": 24,
  "space7": 32,
  "space8": 40
};

export const RadiusScalePx: Readonly<Record<string, number>> = {
  "--radius-sm": 3,
  "--radius-md": 4,
  "--radius-lg": 6,
  "--radius-pill": 999
};

export const Shadows: Readonly<Record<string, string>> = {
  "--shadow-overlay": "0 1px 3px rgba(0,0,0,0.35)"
};

export const Typography: Readonly<Record<string, unknown>> = {
  "fontFamilyBody": "\"Segoe UI\", system-ui, sans-serif",
  "fontFamilyMono": "Consolas, \"Courier New\", monospace",
  "scale": {
    "xs": 0.68,
    "sm": 0.75,
    "body": 0.85,
    "md": 1.0,
    "lg": 1.15
  }
};

export const MotionDurationMs: Readonly<Record<string, number>> = {
  "fast": 120,
  "base": 180,
  "slow": 240
};

export const MotionEasing: Readonly<Record<string, string>> = {
  "arrival": "cubic-bezier(0.16, 1, 0.3, 1)",
  "state": "cubic-bezier(0.4, 0, 0.2, 1)",
  "linear": "linear"
};

export const ZLayers: Readonly<Record<string, number>> = {
  "--z-content": 0,
  "--z-sticky": 10,
  "--z-skip-link": 100,
  "--z-overlay": 500,
  "--z-toast": 600
};

/** CSS :root block consumed by sharedStyles(); codegen only. */
export function tokenCssRoot(): string {
  return `
    :root {
      --bg: #1e1e1e;
      --card: #252526;
      --fg: #e6e6e6;
      --muted: #b0b0b0;
      --border: rgba(200,200,200,0.28);
      --accent: #1177bb;
      --accent-bright: #6cb6ff;
      --accent-fg: #ffffff;
      --focus: #4fc1ff;
      --ok: #3fb950;
      --warn: #e3b341;
      --err: #f85149;
      --border-hover: rgba(200,200,200,0.45);
      --hover-wash: rgba(255,255,255,0.04);
      --ok-border: rgba(63,185,80,0.4);
      --ok-wash: rgba(63,185,80,0.1);
      --warn-border: rgba(227,179,65,0.4);
      --warn-wash: rgba(227,179,65,0.08);
      --err-border: rgba(248,81,73,0.4);
      --err-wash: rgba(248,81,73,0.08);
      --inset-wash: rgba(0,0,0,0.15);

      --surface-base: var(--bg);
      --surface-card: var(--card);
      --text-primary: var(--fg);
      --text-muted: var(--muted);
      --border-default: var(--border);
      --accent-primary: var(--accent);
      --accent-bright-text: var(--accent-bright);
      --border-hover-line: var(--border-hover);
      --hover-wash-bg: var(--hover-wash);
      --ok-border-line: var(--ok-border);
      --ok-wash-bg: var(--ok-wash);
      --warn-border-line: var(--warn-border);
      --warn-wash-bg: var(--warn-wash);
      --err-border-line: var(--err-border);
      --err-wash-bg: var(--err-wash);
      --inset-wash-bg: var(--inset-wash);
      --accent-on-accent: var(--accent-fg);
      --status-ok: var(--ok);
      --status-warn: var(--warn);
      --status-err: var(--err);
      --focus-ring: var(--focus);

      --space-0: 0px;
      --space-1: 4px;
      --space-2: 8px;
      --space-3: 12px;
      --space-4: 16px;
      --space-5: 20px;
      --space-6: 24px;
      --space-7: 32px;
      --space-8: 40px;

      --radius-sm: 3px;
      --radius-md: 4px;
      --radius-lg: 6px;
      --radius-pill: 999px;

      --shadow-overlay: 0 1px 3px rgba(0,0,0,0.35);

      --type-font-family-body: "Segoe UI", system-ui, sans-serif;
      --type-font-family-mono: Consolas, "Courier New", monospace;
      --type-xs: 0.68rem;
      --type-sm: 0.75rem;
      --type-body: 0.85rem;
      --type-md: 1.0rem;
      --type-lg: 1.15rem;

      --motion-duration-fast: 120ms;
      --motion-duration-base: 180ms;
      --motion-duration-slow: 240ms;
      --motion-easing-arrival: cubic-bezier(0.16, 1, 0.3, 1);
      --motion-easing-state: cubic-bezier(0.4, 0, 0.2, 1);
      --motion-easing-linear: linear;

      --z-content: 0;
      --z-sticky: 10;
      --z-skip-link: 100;
      --z-overlay: 500;
      --z-toast: 600;
    }
  `;
}
