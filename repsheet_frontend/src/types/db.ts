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
    climateAndEnergy?: string;
    affordabilityAndHousing?: string;
    defense?: string;
    healthcare?: string;
    immigration?: string;
    infrastructure?: string;
    spendingAndTaxation?: string;
    indigenousRelations?: string;
  };
}
