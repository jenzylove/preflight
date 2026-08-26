import type { Config } from "tailwindcss";

/**
 * The palette is defined once in globals.css as CSS custom properties and
 * surfaced here by name. Tailwind classes then read as intent — `bg-ink-100`,
 * `text-paper-300` — rather than as hex codes scattered through markup.
 */
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          "000": "var(--ink-000)",
          "050": "var(--ink-050)",
          100: "var(--ink-100)",
          150: "var(--ink-150)",
          200: "var(--ink-200)",
          300: "var(--ink-300)",
          400: "var(--ink-400)",
        },
        paper: {
          "000": "var(--paper-000)",
          100: "var(--paper-100)",
          200: "var(--paper-200)",
          300: "var(--paper-300)",
          400: "var(--paper-400)",
        },
        accent: { DEFAULT: "var(--accent)", dim: "var(--accent-dim)" },
        ok: { DEFAULT: "var(--ok)", bg: "var(--ok-bg)" },
        review: { DEFAULT: "var(--review)", bg: "var(--review-bg)" },
        act: { DEFAULT: "var(--act)", bg: "var(--act-bg)" },
        stop: { DEFAULT: "var(--stop)", bg: "var(--stop-bg)" },
        think: { DEFAULT: "var(--think)", bg: "var(--think-bg)" },
        idle: { DEFAULT: "var(--idle)", bg: "var(--idle-bg)" },
        line: { DEFAULT: "var(--line)", strong: "var(--line-strong)" },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "Georgia", "serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        // A display scale that can carry a cinematic headline without needing
        // arbitrary values at every call site.
        "display-sm": ["2.5rem", { lineHeight: "1.08", letterSpacing: "-0.02em" }],
        "display-md": ["3.5rem", { lineHeight: "1.04", letterSpacing: "-0.025em" }],
        "display-lg": ["4.75rem", { lineHeight: "1.0", letterSpacing: "-0.03em" }],
        "display-xl": ["6.5rem", { lineHeight: "0.96", letterSpacing: "-0.035em" }],
      },
      maxWidth: { measure: "var(--measure)" },
      transitionTimingFunction: {
        // Slow out, almost no bounce. Projector motion, not app motion.
        cinema: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
} satisfies Config;
