export interface Member {
  "Member ID": string;
  "Honorific Title": string | null;
  "First Name": string;
  "Last Name": string;
  Constituency: string;
  "Province / Territory": string;
  "Political Affiliation": string;
  "Start Date": string;
  "End Date": string | null;
  Summary: string | null;
  "Short Summary": string | null;
  "Photo URL": string | null;
  "Votes Attended": number;
  "Votes Attendable": number;
  "Private Bill Count": number;
  "Parliament Count": number;
}

export interface MemberSummary {
  summary: string;
  issues: Record<Issues, string | null>;
}

export interface Bill {
  "Bill ID": string;
  Parliament: number;
  Session: number;
  "Bill Number": string;
  "Bill Type": string;
  "Private Bill Sponsor Member ID": string | null;
  "Long Title": string;
  "Short Title": string | null;
  "Bill External URL": string;
  "First Reading Date": string;
  Summary: string | null;
}

export const issues = [
  "inflationAndCostOfLiving",
  "jobs",
  "taxation",
  "spending",
  "healthcare",
  "childcare",
  "seniorsAndPensions",
  "climate",
  "environmentalProtection",
  "energy",
  "reconciliation",
  "immigrationAndIntegration",
  "incomeInequalityAndPoverty",
  "reproductiveRights",
  "genderAndSexuality",
  "racism",
  "crime",
  "gunControl",
  "defense",
  "foreignAid",
] as const;

export const issueGroups: Record<string, Issues[]> = {
  economy: ["inflationAndCostOfLiving", "jobs", "taxation", "spending"],
  socialServices: ["healthcare", "childcare", "seniorsAndPensions"],
  environment: ["climate", "environmentalProtection", "energy"],
  socialJustice: [
    "reconciliation",
    "immigrationAndIntegration",
    "incomeInequalityAndPoverty",
    "reproductiveRights",
    "genderAndSexuality",
    "racism",
  ],
  securityAndDefense: ["crime", "gunControl", "defense", "foreignAid"],
} as const;

export type Issues = (typeof issues)[number];

export interface BillSummary {
  summary: string;
  issues: Record<Issues, string | null>;
}
