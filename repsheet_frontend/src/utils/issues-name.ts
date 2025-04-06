import type { BillSummary } from "../types/db";

export const issueName: Record<keyof BillSummary["issues"], string> = {
  climateAndEnergy: "Climate and Energy",
  affordabilityAndHousing: "Affordability and Housing",
  defense: "Defense",
  healthcare: "Healthcare",
  immigration: "Immigration",
  infrastructure: "Infrastructure",
  spendingAndTaxation: "Spending and Taxation",
  indigenousRelations: "Indigenous Relations",
};
