/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{astro,html,js,jsx,ts,tsx,vue,svelte,md,mdx}"],
  theme: {
    extend: {
      colors: {
        loki: {
          bg: "#FAFAFA",
          surface: "#FFFFFF",
          elevated: "#F0F0F0",
          muted: "#F5F5F5",
        },
        txt: {
          DEFAULT: "#111111",
          secondary: "#4A4A4A",
          tertiary: "#888888",
        },
        edge: {
          DEFAULT: "#DCDCDC",
          light: "#ECECEC",
          hover: "#BBBBBB",
        },
        impact: {
          alto: "#DC2626",
          "alto-bg": "rgba(220, 38, 38, 0.07)",
          medio: "#CA8A04",
          "medio-bg": "rgba(202, 138, 4, 0.07)",
          bajo: "#16A34A",
          "bajo-bg": "rgba(22, 163, 74, 0.07)",
        },
        accent: {
          DEFAULT: "#1a56db",
          light: "rgba(26, 86, 219, 0.06)",
        },
      },
      fontFamily: {
        display: ["Newsreader", "Georgia", "serif"],
        sans: ["Outfit", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        tightest: "-0.03em",
      },
      borderRadius: {
        pill: "100px",
      },
    },
  },
  plugins: [],
};
