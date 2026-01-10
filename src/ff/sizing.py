"""Sizing: how many reps does a launch need?

    workload (calls a year) = sum over segments of  providers x share targeted x calls per provider per year
    reps needed             = workload / (calls a rep makes a day x field days a year)

The call plan (calls a year and share targeted, per segment) lives in data/ref/segments.csv; rep capacity (calls a
day, field days) in data/ref/franchises.csv. They are assumptions, written down and changeable, not facts about any
company. The same arithmetic runs in Excel (excel/Field-Force-Sizing-Model.xlsx) and tools/verify_workbook.py checks
the two agree.

Public data here says who the providers are and where, not what each one prescribes, so "targeted share" for
generalists is a flat assumption (the top quarter by volume) rather than a ranking of individual doctors.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace

from .sources import MARTS, REF


@dataclass(frozen=True)
class Franchise:
    key: str
    label: str
    places_measure: str
    calls_per_rep_day: float
    field_days: float
    patient_label: str

    @property
    def capacity(self) -> float:
        """Calls one rep makes in a year."""
        return self.calls_per_rep_day * self.field_days


@dataclass(frozen=True)
class SegmentRule:
    franchise: str
    segment: str
    tier: str
    calls_per_year: float
    targeted_share: float


def load_franchises() -> dict[str, Franchise]:
    with (REF / "franchises.csv").open(encoding="utf-8", newline="") as fh:
        return {r["franchise"]: Franchise(r["franchise"], r["label"], r["places_measure"], float(r["calls_per_rep_day"]),
                                          float(r["field_days"]), r["patient_label"]) for r in csv.DictReader(fh)}


def load_rules() -> dict[tuple[str, str], SegmentRule]:
    out: dict[tuple[str, str], SegmentRule] = {}
    with (REF / "segments.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            key = (r["franchise"], r["segment"])
            out[key] = SegmentRule(r["franchise"], r["segment"], r["tier"], float(r["calls_per_year"]),
                                   float(r["targeted_share"]))
    return out


def load_county_segments() -> list[dict]:
    with (MARTS / "county_segment.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["hcps"] = int(r["hcps"])
    return rows


def load_counties(franchise: str) -> dict[str, dict]:
    """County facts for one franchise: where it is, who lives there, and how many patients its measure implies."""
    with (MARTS / "county.csv").open(encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["franchise"] == franchise]
    out = {}
    for r in rows:
        out[r["county"]] = {"state": r["state"], "name": r["name"], "lat": float(r["lat"]), "lon": float(r["lon"]),
                            "pop": int(r["pop"]), "adults": int(r["adults"]), "patients": float(r["patients"]),
                            "prevalence": float(r["prevalence"]), "imputed": r["prevalence_imputed"].lower() == "true"}
    return out


def with_overrides(rules: dict[tuple[str, str], SegmentRule], calls: dict[str, float] | None = None,
                   share: dict[str, float] | None = None) -> dict[tuple[str, str], SegmentRule]:
    """Copy of the rules with calls a year and/or targeted share replaced for named segments."""
    out = {}
    for key, r in rules.items():
        out[key] = replace(r, calls_per_year=(calls or {}).get(r.segment, r.calls_per_year),
                           targeted_share=(share or {}).get(r.segment, r.targeted_share))
    return out


def county_workload(franchise: str, county_segments: list[dict], rules: dict[tuple[str, str], SegmentRule]) -> dict[str, float]:
    """Calls a year needed in each county for one franchise."""
    out: dict[str, float] = {}
    for r in county_segments:
        if r["franchise"] != franchise:
            continue
        rule = rules[(franchise, r["segment"])]
        out[r["county"]] = out.get(r["county"], 0.0) + r["hcps"] * rule.targeted_share * rule.calls_per_year
    return out


def reps_needed(total_calls: float, franchise: Franchise) -> float:
    return total_calls / franchise.capacity


def by_segment(franchise: str, county_segments: list[dict], rules: dict[tuple[str, str], SegmentRule]) -> list[dict]:
    """National table: providers, targeted providers, calls, per segment."""
    agg: dict[str, int] = {}
    for r in county_segments:
        if r["franchise"] == franchise:
            agg[r["segment"]] = agg.get(r["segment"], 0) + r["hcps"]
    rows = []
    for seg, n in sorted(agg.items()):
        rule = rules[(franchise, seg)]
        rows.append({"segment": seg, "tier": rule.tier, "providers": n, "share": rule.targeted_share,
                     "targeted": n * rule.targeted_share, "calls_per_year": rule.calls_per_year,
                     "calls": n * rule.targeted_share * rule.calls_per_year})
    return rows


def by_state(franchise: str, county_segments: list[dict], rules: dict[tuple[str, str], SegmentRule],
             fr: Franchise) -> dict[str, dict]:
    """Calls and reps by state."""
    calls: dict[str, float] = {}
    for r in county_segments:
        if r["franchise"] != franchise:
            continue
        rule = rules[(franchise, r["segment"])]
        calls[r["state"]] = calls.get(r["state"], 0.0) + r["hcps"] * rule.targeted_share * rule.calls_per_year
    return {s: {"calls": c, "reps": c / fr.capacity} for s, c in sorted(calls.items())}
