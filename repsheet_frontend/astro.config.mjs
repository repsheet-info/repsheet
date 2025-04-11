// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";

// https://astro.build/config
export default defineConfig({
  integrations: [
    starlight({
      title: "Repsheet Canada",
      customCss: ["./src/styles/variables.css", "./src/styles/layout.css"],
      social: {
        github: "https://github.com/RepSheet-info/repsheet",
      },
      sidebar: [],
      lastUpdated: true,
      pagination: false,
      tableOfContents: false,
      components: {
        PageTitle: "./src/components/overrides/PageTitle.astro",
        PageFrame: "./src/components/overrides/PageFrame.astro",
      },
    }),
  ],
  redirects: {
    "/": {
      status: 302,
      destination: "/canada",
    },
  },
});
