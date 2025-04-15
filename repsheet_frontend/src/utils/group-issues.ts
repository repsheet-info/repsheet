import { issueGroups, type Issues } from "../types/db";

export function groupIssues(issues?: Record<Issues, string | null>) {
  if (!issues) return {};

  // Group issues by their category
  const groupedIssues: Record<string, Issues[]> = {};
  Object.entries(issueGroups).forEach(([groupName, groupIssues]) => {
    const memberIssuesInGroup = groupIssues.filter(
      (issue) => issues[issue as Issues] !== null
    );
    if (memberIssuesInGroup.length > 0) {
      groupedIssues[groupName] = memberIssuesInGroup;
    }
  });

  return groupedIssues;
}
