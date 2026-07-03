/** @type {import('tailwindcss').Config} */
export default {
  // Dark mode is the base theme for the command center; we force it on via the
  // `dark` class on <html> and use the `dark:` variants throughout.
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Command-center surface palette (deep slate/navy).
        surface: {
          950: "#070b14",
          900: "#0b1220",
          800: "#111a2e",
          700: "#1b2740",
          600: "#26344f",
        },
        // Risk status bands (Requirement 3.4 / 4.1) - referenced by the
        // band-to-color helper in a later task.
        band: {
          low: "#22c55e",
          elevated: "#f59e0b",
          high: "#ef4444",
        },
        accent: {
          DEFAULT: "#38bdf8",
          muted: "#0ea5e9",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
