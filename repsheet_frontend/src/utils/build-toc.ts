import type { StarlightRouteData } from "@astrojs/starlight/route-data";
import type { Issues } from "../types/db";
import { issueName } from "./issue-name";
import { groupName } from "./group-name";

type TocItem = Exclude<StarlightRouteData["toc"], undefined>["items"][number];

export function buildToc(groupedIssues: Record<string, Issues[]>): TocItem[] {
  const toc: TocItem[] = [];

  Object.entries(groupedIssues).forEach(([name, groupIssues]) => {
    toc.push({
      depth: 1,
      slug: name,
      text: groupName[name as keyof typeof groupName],
      children: groupIssues.map((issue) => ({
        depth: 2,
        slug: issue,
        text: issueName[issue],
        children: [],
      })),
    });
  });

  return toc;
}
