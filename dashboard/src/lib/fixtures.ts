import fs from "node:fs";
import path from "node:path";
import { Alignment, Counties, Headline, Meta, Quality, Sizing, type Dataset } from "./schema";

// The real data files, for tests. (lib/load.ts is server-only and cannot be imported from a test.)
const DIR = path.join(process.cwd(), "public", "data");
const read = <T>(file: string, schema: { parse: (v: unknown) => T }): T => schema.parse(JSON.parse(fs.readFileSync(path.join(DIR, file), "utf-8")));

export function realDataset(): Dataset {
  return {
    headline: read("headline.json", Headline),
    sizing: read("sizing.json", Sizing),
    alignment: read("alignment.json", Alignment),
    counties: read("counties.json", Counties),
    quality: read("quality.json", Quality),
    meta: read("meta.json", Meta),
    workbookKb: 41,
  };
}
