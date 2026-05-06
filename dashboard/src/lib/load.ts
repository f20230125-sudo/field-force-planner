import "server-only";
import fs from "node:fs";
import path from "node:path";
import { Alignment, Counties, Headline, Meta, Quality, Sizing, type Dataset } from "./schema";

const DIR = path.join(process.cwd(), "public", "data");

function read<T>(file: string, schema: { parse: (v: unknown) => T }): T {
  const raw = JSON.parse(fs.readFileSync(path.join(DIR, file), "utf-8"));
  try {
    return schema.parse(raw);
  } catch (e) {
    throw new Error(`${file} does not match its schema: ${e instanceof Error ? e.message : String(e)}`);
  }
}

/** Reads and validates every data file. Runs at build time on the server; the page ships the result. */
export function loadDataset(): Dataset {
  const counties = read("counties.json", Counties);
  const xlsx = path.join(process.cwd(), "public", "downloads", "Field-Force-Sizing-Model.xlsx");
  return {
    headline: read("headline.json", Headline),
    sizing: read("sizing.json", Sizing),
    alignment: read("alignment.json", Alignment),
    counties,
    quality: read("quality.json", Quality),
    meta: read("meta.json", Meta),
    workbookKb: Math.round(fs.statSync(xlsx).size / 1000),
  };
}
