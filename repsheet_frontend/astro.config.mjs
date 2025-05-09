// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";

// https://astro.build/config
export default defineConfig({
  site: "https://repsheet.info",
  integrations: [
    starlight({
      title: "Repsheet Canada",
      customCss: ["./src/styles/variables.css", "./src/styles/layout.css"],
      social: {
        github: "https://github.com/RepSheet-info/repsheet",
      },
      sidebar: [
        {
          label: "Home",
          slug: "",
        },
        {
          label: "About",
          link: "/canada/about/",
        },
        {
          label: "Methodology",
          link: "/canada/methodology/",
        },
        {
          label: "Party Leaders",
          items: [
            {
              link: "/canada/representative/maxime_bernier/",
              label: "Maxime Bernier",
            },
            {
              link: "/canada/representative/Yves-François_Blanchet/",
              label: "Yves-François Blanchet",
            },
            {
              link: "/canada/representative/mark_carney/",
              label: "Mark Carney",
            },
            {
              link: "/canada/representative/Elizabeth_May/",
              label: "Elizabeth May",
            },
            {
              link: "/canada/representative/Pierre_Poilievre/",
              label: "Pierre Poilievre",
            },
            {
              link: "/canada/representative/Jagmeet_Singh/",
              label: "Jagmeet Singh",
            },
          ],
        },
        {
          label: "Feedback",
          link: "https://forms.gle/spefTkVXmnWjLS5C8",
          attrs: {
            target: "_blank",
            rel: "noopener noreferrer",
          },
        },
      ],
      lastUpdated: true,
      pagination: false,
      tableOfContents: true,
      components: {
        PageTitle: "./src/components/overrides/PageTitle.astro",
        PageFrame: "./src/components/overrides/PageFrame.astro",
        Head: "./src/components/overrides/Head.astro",
      },
    }),
  ],
  redirects: {
    "/canada": {
      status: 302,
      destination: "/",
    },
  },
});
