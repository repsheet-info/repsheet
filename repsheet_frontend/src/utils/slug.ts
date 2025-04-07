import type { Member } from "../types/db";

export function makeMemberSlug(member: Member) {
  return `${member["First Name"]}_${member["Last Name"]}`;
}
