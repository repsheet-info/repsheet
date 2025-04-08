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

export type Issues =
  | "climateAndEnergy"
  | "affordabilityAndHousing"
  | "defense"
  | "healthcare"
  | "immigration"
  | "infrastructure"
  | "spendingAndTaxation"
  | "indigenousRelations"
  | "crimeAndJustice"
  | "civilRights";

export interface BillSummary {
  summary: string;
  issues: Record<Issues, string | null>;
}
