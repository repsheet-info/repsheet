import { defineCollection } from "astro:content";
import { docsLoader } from "@astrojs/starlight/loaders";
import { docsSchema } from "@astrojs/starlight/schema";
import { z } from "astro/zod";

// Extend the default Starlight schema
const extendedSchema = docsSchema({
  extend: z.object({
    subtitle: z.string().optional().nullable(),
    toc: z
      .object({
        items: z.array(
          z.object({
            depth: z.number(),
            slug: z.string(),
            text: z.string(),
            children: z.array(
              z.object({
                depth: z.number(),
                slug: z.string(),
                text: z.string(),
              })
            ),
          })
        ),
      })
      .optional(),
  }),
});

export const collections = {
  docs: defineCollection({
    loader: docsLoader(),
    schema: extendedSchema,
  }),
  redirects: {
    "/": "/canada/",
  },
};
