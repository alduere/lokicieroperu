import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";

export default defineConfig({
  site: "https://alduere.github.io",
  base: "/lokicieroperu",
  trailingSlash: "ignore",
  integrations: [tailwind()],
  output: "static",
  build: {
    format: "directory",
  },
});
