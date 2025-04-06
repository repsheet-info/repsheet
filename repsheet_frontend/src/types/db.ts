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
}

export interface Bill {
  "Bill ID": string;
  Summary: string;
}

export interface BillSummary {
  title: string;
  summary: string;
  sponsor: string[];
  issues: {
    climateAndEnergy: string | null;
    affordabilityAndHousing: string | null;
    defense: string | null;
    healthcare: string | null;
    immigration: string | null;
    infrastructure: string | null;
    spendingAndTaxation: string | null;
    indigenousRelations: string | null;
  };
}
