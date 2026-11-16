/** @type {import('tailwindcss').Config} */
// Colores definidos como variables CSS «r g b» por src/lib/theme.ts (tema claro/oscuro y acento).
const v = (n) => `rgb(var(--${n}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: Object.fromEntries(["bg", "panel", "panel2", "line", "line2", "ink", "dim", "faint", "acc", "acc2", "onacc",
        "warn", "err", "info", "violet", "cyan", "orange"].map((k) => [k, v(k)])),
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: { "2xs": ["10.5px", "14px"] },
    },
  },
  plugins: [],
};
