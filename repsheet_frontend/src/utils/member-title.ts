import type { Member } from "../types/db";

export function memberTitle(member: Member) {
  return `${member["Honorific Title"] ?? ""} ${member["First Name"]} ${
    member["Last Name"]
  }`.trim();
}
