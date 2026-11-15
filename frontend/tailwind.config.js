/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#05080a",
        panel: "#0a1013",
        panel2: "#0e161a",
        line: "#18242a",
        line2: "#22323a",
        ink: "#d6e2dd",
        dim: "#7f9089",
        faint: "#4c5c56",
        acc: "#2fe39a",
        acc2: "#1fb67a",
        warn: "#f0b44c",
        err: "#ff6b6b",
        info: "#58b4ff",
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: { "2xs": ["10.5px", "14px"] },
    },
  },
  plugins: [],
};
