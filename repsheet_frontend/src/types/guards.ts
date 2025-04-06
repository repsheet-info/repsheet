import type { Bill, BillSummary, Member } from "./db";

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

  if (typeof bill["Summary"] !== "string") {
    throw new Error("Object is not of type Bill - Summary must be a string");
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

  if (typeof summary.title !== "string") {
    throw new Error(
      "Object is not of type BillSummary - title must be a string"
    );
  }

  if (typeof summary.summary !== "string") {
    throw new Error(
      "Object is not of type BillSummary - summary must be a string"
    );
  }

  if (
    !Array.isArray(summary.sponsor) ||
    !summary.sponsor.every((s) => typeof s === "string")
  ) {
    throw new Error(
      "Object is not of type BillSummary - sponsor must be an array of strings"
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
