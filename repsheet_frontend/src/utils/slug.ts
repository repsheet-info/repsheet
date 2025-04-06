import { Member } from "../types/db";

export function makeMemberSlug(member: Member) {
  return `${member["First Name"].toLowerCase()}-${member[
    "Last Name"
  ].toLowerCase()}`;
}
