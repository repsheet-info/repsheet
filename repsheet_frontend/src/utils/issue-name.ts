import type { BillSummary } from "../types/db";

export const issueName: Record<keyof BillSummary["issues"], string> = {
  inflationAndCostOfLiving: "Inflation and Cost of Living",
  jobs: "Jobs",
  taxation: "Taxation",
  spending: "Spending",
  healthcare: "Healthcare",
  childcare: "Childcare",
  seniorsAndPensions: "Seniors and Pensions",
  climate: "Climate",
  environmentalProtection: "Environmental Protection",
  energy: "Energy",
  reconciliation: "Reconciliation",
  immigrationAndIntegration: "Immigration and Integration",
  incomeInequalityAndPoverty: "Income Inequality and Poverty",
  reproductiveRights: "Reproductive Rights",
  genderAndSexuality: "Gender and Sexuality",
  racism: "Racism",
  crime: "Crime",
  gunControl: "Gun Control",
  defense: "Defense",
  foreignAid: "Foreign Aid",
};
