export const franchiseKeys = ["diabetes", "oncology"] as const;
export type Franchise = (typeof franchiseKeys)[number];
