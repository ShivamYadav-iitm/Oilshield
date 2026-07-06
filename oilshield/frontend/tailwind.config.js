/** @type {import('tailwindcss').Config} */
export default {
  // Light is the base theme for the command center. Components use the design
  // tokens directly (not `dark:` variants), so no `dark` class is forced on
  // <html>; the palette below drives the whole clean, premium light theme.
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Command-center surface palette — a clean, premium LIGHT scale. The
        // token NAMES are kept stable (950/900/800/700/600) so existing
        // class usage still resolves; the VALUES are set by usage:
        //   950 = page background (very light cool gray, faint teal)
        //   900 = card / panel base (white)
        //   800 = raised / hover
        //   700 = borders / hairlines
        //   600 = strong borders / muted strokes
        surface: {
          950: "#EEF2F4", // page background (very light cool gray)
          900: "#FFFFFF", // panel / card base
          800: "#F1F5F9", // raised / hover
          700: "#E2E8F0", // borders / hairlines
          600: "#CBD5E1", // strong borders / muted strokes
        },
        // Risk status bands (Requirement 3.4 / 4.1) — saturated semantic hues
        // that read well on the light shell and on the light map. Kept in sync
        // with BAND_HEX in src/lib/format.ts.
        band: {
          low: "#10B981", // emerald
          elevated: "#F59E0B", // amber (darkened for contrast on white)
          high: "#F43F5E", // rose/red
        },
        // Brand / primary — TEAL (the "energy" signature for the light theme).
        // Primary buttons use WHITE text on the teal fill.
        accent: {
          DEFAULT: "#0D9488",
          muted: "#0F766E",
          50: "#F0FDFA",
          100: "#CCFBF1",
          200: "#99F6E4",
          300: "#5EEAD4",
          400: "#2DD4BF",
          500: "#14B8A6",
          600: "#0D9488",
          700: "#0F766E",
          800: "#115E59",
          900: "#134E4A",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Space Grotesk", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 2px rgba(15,23,42,0.04), 0 8px 24px -18px rgba(15,23,42,0.14)",
        // Elevated "glass card" stack — soft, layered LIGHT shadows for gentle
        // depth over the near-white base.
        glass:
          "0 1px 2px rgba(15,23,42,0.04), 0 12px 30px -18px rgba(15,23,42,0.18)",
        "glass-hover":
          "0 1px 3px rgba(15,23,42,0.06), 0 20px 44px -20px rgba(15,23,42,0.24)",
        // Colored ambient glows — softened / lightened one per module accent +
        // status band. Used on KPI / procurement cards where a standalone
        // colored halo reads well on white.
        "glow-amber": "0 0 26px -10px rgba(245,158,11,0.30)",
        "glow-rose": "0 0 26px -10px rgba(244,63,94,0.28)",
        "glow-emerald": "0 0 26px -10px rgba(16,185,129,0.26)",
        "glow-violet": "0 0 26px -10px rgba(139,92,246,0.26)",
        "glow-sky": "0 0 26px -10px rgba(14,165,233,0.26)",
        // Combined depth + colored glow for glass panels on hover (one class
        // sets the full box-shadow so the accent halo layers over the depth).
        "glass-amber":
          "0 1px 3px rgba(15,23,42,0.06), 0 20px 44px -20px rgba(15,23,42,0.24), 0 0 28px -14px rgba(245,158,11,0.35)",
        "glass-rose":
          "0 1px 3px rgba(15,23,42,0.06), 0 20px 44px -20px rgba(15,23,42,0.24), 0 0 28px -14px rgba(244,63,94,0.35)",
        "glass-emerald":
          "0 1px 3px rgba(15,23,42,0.06), 0 20px 44px -20px rgba(15,23,42,0.24), 0 0 28px -14px rgba(16,185,129,0.32)",
        "glass-violet":
          "0 1px 3px rgba(15,23,42,0.06), 0 20px 44px -20px rgba(15,23,42,0.24), 0 0 28px -14px rgba(139,92,246,0.32)",
        "glass-sky":
          "0 1px 3px rgba(15,23,42,0.06), 0 20px 44px -20px rgba(15,23,42,0.24), 0 0 28px -14px rgba(14,165,233,0.32)",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
      },
    },
  },
  plugins: [],
};
