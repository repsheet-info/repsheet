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
      sidebar: [
        {
          label: "Home",
          slug: "canada",
        },
        {
          label: "About",
          slug: "canada/about",
        },
        {
          label: "Methodology",
          slug: "canada/methodology",
        },
        {
          label: "Party Leaders",
          items: [
            {
              slug: "canada/representative/maxime_bernier",
              label: "Maxime Bernier",
            },
            {
              link: "/canada/representative/Yves-François_Blanchet",
              label: "Yves-François Blanchet",
            },
            { slug: "canada/representative/mark_carney", label: "Mark Carney" },
            {
              link: "/canada/representative/Elizabeth_May",
              label: "Elizabeth May",
            },
            {
              link: "/canada/representative/Pierre_Poilievre",
              label: "Pierre Poilievre",
            },
            {
              link: "/canada/representative/Jagmeet_Singh",
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
