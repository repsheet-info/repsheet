import type { Bill, BillSummary, Member, MemberSummary } from "./db";

export function assertIsMember(member: any): asserts member is Member {
  if (!member || typeof member !== "object") {
    throw new Error("Object is not of type Member - Member must be an object");
  }

  if (typeof member["Member ID"] !== "string") {
    throw new Error(
      "Object is not of type Member - Member ID must be a string"
    );
  }

  if (
    member["Honorific Title"] !== null &&
    typeof member["Honorific Title"] !== "string"
  ) {
    throw new Error(
      "Object is not of type Member - Honorific Title must be a string or null"
    );
  }

  if (typeof member["First Name"] !== "string") {
    throw new Error(
      "Object is not of type Member - First Name must be a string"
    );
  }

  if (typeof member["Last Name"] !== "string") {
    throw new Error(
      "Object is not of type Member - Last Name must be a string"
    );
  }

  if (typeof member["Constituency"] !== "string") {
    throw new Error(
      "Object is not of type Member - Constituency must be a string"
    );
  }

  if (typeof member["Province / Territory"] !== "string") {
    throw new Error(
      "Object is not of type Member - Province / Territory must be a string"
    );
  }

  if (typeof member["Political Affiliation"] !== "string") {
    throw new Error(
      "Object is not of type Member - Political Affiliation must be a string"
    );
  }

  if (typeof member["Start Date"] !== "string") {
    throw new Error(
      "Object is not of type Member - Start Date must be a string"
    );
  }

  if (member["End Date"] !== null && typeof member["End Date"] !== "string") {
    throw new Error(
      "Object is not of type Member - End Date must be a string or null"
    );
  }
}

export function assertIsBill(bill: any): asserts bill is Bill {
  if (!bill || typeof bill !== "object") {
    throw new Error("Object is not of type Bill - Bill must be an object");
  }

  if (typeof bill["Bill ID"] !== "string") {
    throw new Error("Object is not of type Bill - Bill ID must be a string");
  }

  if (typeof bill["Parliament"] !== "number") {
    throw new Error("Object is not of type Bill - Parliament must be a number");
  }

  if (typeof bill["Session"] !== "number") {
    throw new Error("Object is not of type Bill - Session must be a number");
  }

  if (typeof bill["Bill Number"] !== "string") {
    throw new Error(
      "Object is not of type Bill - Bill Number must be a string"
    );
  }

  if (typeof bill["Bill Type"] !== "string") {
    throw new Error("Object is not of type Bill - Bill Type must be a string");
  }

  if (
    bill["Private Bill Sponsor Member ID"] !== null &&
    typeof bill["Private Bill Sponsor Member ID"] !== "string"
  ) {
    throw new Error(
      "Object is not of type Bill - Private Bill Sponsor Member ID must be a string or null"
    );
  }

  if (typeof bill["Long Title"] !== "string") {
    throw new Error("Object is not of type Bill - Long Title must be a string");
  }

  if (bill["Short Title"] !== null && typeof bill["Short Title"] !== "string") {
    throw new Error(
      "Object is not of type Bill - Short Title must be a string or null"
    );
  }

  if (typeof bill["Bill External URL"] !== "string") {
    throw new Error(
      "Object is not of type Bill - Bill External URL must be a string"
    );
  }

  if (typeof bill["First Reading Date"] !== "string") {
    throw new Error(
      "Object is not of type Bill - First Reading Date must be a string"
    );
  }

  if (bill["Summary"] !== null && typeof bill["Summary"] !== "string") {
    throw new Error(
      "Object is not of type Bill - Summary must be a string or null"
    );
  }
}

export function assertIsBillSummary(
  summary: any
): asserts summary is BillSummary {
  if (!summary || typeof summary !== "object") {
    throw new Error(
      "Object is not of type BillSummary - BillSummary must be an object"
    );
  }

  if (typeof summary.summary !== "string") {
    throw new Error(
      "Object is not of type BillSummary - summary must be a string"
    );
  }

  if (summary.issues && typeof summary.issues !== "object") {
    throw new Error(
      "Object is not of type BillSummary - issues must be an object"
    );
  }

  // Check each optional issue field is a string if present
  const issueFields = [
    "climateAndEnergy",
    "affordabilityAndHousing",
    "defense",
    "healthcare",
    "immigration",
    "infrastructure",
    "spendingAndTaxation",
    "indigenousRelations",
  ];

  for (const field of issueFields) {
    if (
      summary.issues?.[field] !== undefined &&
      typeof summary.issues[field] !== "string" &&
      summary.issues[field] !== null
    ) {
      throw new Error(
        `Object is not of type BillSummary - issues.${field} must be a string or null if present`
      );
    }
  }
}

export function assertIsMemberSummary(
  summary: any
): asserts summary is MemberSummary {
  if (!summary || typeof summary !== "object") {
    throw new Error(
      "Object is not of type MemberSummary - MemberSummary must be an object"
    );
  }

  if (typeof summary.summary !== "string") {
    throw new Error(
      "Object is not of type MemberSummary - summary must be a string"
    );
  }

  if (summary.issues && typeof summary.issues !== "object") {
    throw new Error(
      "Object is not of type MemberSummary - issues must be an object"
    );
  }

  // Check each optional issue field is a string if present
  const issueFields = [
    "climateAndEnergy",
    "affordabilityAndHousing",
    "defense",
    "healthcare",
    "immigration",
    "infrastructure",
    "spendingAndTaxation",
    "indigenousRelations",
    "crimeAndJustice",
    "civilRights",
  ];

  for (const field of issueFields) {
    if (
      summary.issues?.[field] !== undefined &&
      typeof summary.issues[field] !== "string" &&
      summary.issues[field] !== null
    ) {
      throw new Error(
        `Object is not of type MemberSummary - issues.${field} must be a string or null if present`
      );
    }
  }
}
