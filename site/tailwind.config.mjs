/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{astro,html,js,jsx,ts,tsx,vue,svelte,md,mdx}"],
  theme: {
    extend: {
      colors: {
        loki: {
          bg: "#0c0d12",
          surface: "#14151c",
          elevated: "#1c1d26",
          card: "#1a1b23",
        },
        txt: {
          DEFAULT: "#e8e8ec",
          muted: "#8b8c99",
          dim: "#55566a",
        },
        edge: {
          DEFAULT: "#25262f",
          light: "#1e1f28",
          hover: "#32333f",
        },
        impact: {
          alto: "#f87171",
          "alto-bg": "rgba(248, 113, 113, 0.12)",
          medio: "#fbbf24",
          "medio-bg": "rgba(251, 191, 36, 0.12)",
          bajo: "#4ade80",
          "bajo-bg": "rgba(74, 222, 128, 0.12)",
        },
        accent: {
          DEFAULT: "#818cf8",
          muted: "rgba(129, 140, 248, 0.15)",
        },
      },
      fontFamily: {
        display: ["Bricolage Grotesque", "system-ui", "sans-serif"],
        sans: ["DM Sans", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        tightest: "-0.04em",
      },
      borderRadius: {
        pill: "100px",
      },
    },
  },
  plugins: [],
};
