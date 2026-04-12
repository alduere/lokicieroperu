/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{astro,html,js,jsx,ts,tsx,vue,svelte,md,mdx}"],
  theme: {
    extend: {
      colors: {
        parchment: {
          DEFAULT: "#f5f0e6",
          light: "#faf5eb",
        },
        ink: {
          DEFAULT: "#2c1810",
          light: "#4a3f30",
          sepia: "#7a6b55",
          rule: "#c4b69c",
          "rule-light": "#d8ccb8",
        },
        impact: {
          alto: "#8b2020",
          medio: "#9a6b1a",
          bajo: "#3a6b3a",
        },
      },
      fontFamily: {
        display: ["Playfair Display", "Georgia", "serif"],
        sans: ["Source Sans 3", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        tightest: "-0.04em",
      },
    },
  },
  plugins: [],
};
