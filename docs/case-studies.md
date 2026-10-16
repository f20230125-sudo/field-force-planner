# Case studies: what went wrong, and how it was found

The order to tell these in if you have ten minutes: Connecticut (1), Florida (2), Hawaii and the Aleutians (4), why counties had to be split (5), the honest validation (6).

## 1. Eight counties vanished in a join

**What happened.** Joining the Census Gazetteer to the population file kept 3,135 counties, not 3,143.

**How it was found.** The scorecard compares counties kept with counties in the population file (check C12). It failed by exactly eight.

**What it was.** Connecticut replaced its eight counties with nine planning regions in 2022. The 2023 Gazetteer follows that; the population file, the ZIP crosswalk and the adjacency file do not. A join on county code lost the whole state without an error.

**Fix.** Every source is pinned to the old Connecticut counties: the 2021 Gazetteer, the 2023 CDC PLACES release, the 2020 ZIP crosswalk. The choice is written at the top of `sources.py`, and the README lists the vintages.

## 2. All of Florida was filled with the national median

**What happened.** The scorecard warned that 7.4% of diabetes patients sat in counties with no prevalence estimate (check C14). Sixty-seven counties, all in one state.

**What it was.** Florida did not release its 2021 survey data, so the 2023 PLACES release has no Florida counties. My fallback (state median, then national median) found no Florida values and used the national median for the whole state: a wrong number applied confidently to a state with 8% of the patients.

**Fix.** Florida takes its 2022 estimates from the 2024 release, on the same county codes; each county records which survey year it came from; the fallback remains for any future gap and is flagged.

## 3. 52 states

**What happened.** A test asserting 51 distinct states (50 plus DC) failed with 52.

**What it was.** The Gazetteer lists Puerto Rico. Its 41,000 providers never reached the county table, so the sizing was unaffected, but "active individuals in the 50 states and DC" was untrue. The scope now comes from the county table, not the Gazetteer.

## 4. Hawaii attached to the Aleutian Islands

**What happened.** The alignment tied each island to its nearest county so the graph is connected. Hawaii's nearest county, once Alaska had been tied on, was 4,364 km away in the Aleutians.

**Fix.** A region more than 300 km from the mainland is aligned on its own, with territories in proportion to its workload (at least one). Alaska gets 3 diabetes territories, Hawaii 5; near islands (Nantucket-type counties) still get a distance link, and every link is reported. Two tests cover it: a near island is bridged, a far region stands alone.

## 5. Big-city counties are worth dozens of territories

**What happened.** With 1,310 territories, Los Angeles County alone carries more than three percent of the work, about forty territories' worth. A county cannot be balanced if it cannot be split.

**What I did.** A county heavier than a set fraction of a territory is cut into equal pieces that touch each other and the neighbours. With pieces of 0.4 the territory-weight spread (coefficient of variation) was 12.4% for oncology; 0.25 gave 9.2%, 0.15 gave 6.6%, 0.1 gave 6.1% at the cost of hundreds more split counties, so 0.15 it is. The cost is stated: 865 counties are split for diabetes, and territories are less compact (mean radius 36 km against 29 km for the baseline).

## 6. Does public prevalence predict where the money is?

**What I tested.** Whether demand built from CDC prevalence ranks the states like observed Medicaid drug spend (from Rx Market Pulse).

**What came out.** State size: rank correlation 0.86 (diabetes) and 0.95 (oncology), which is mostly population. Spend per enrollee against prevalence: -0.10 and -0.04, nothing. Formulary, benefit design and who is enrolled dominate, not how common the disease is.

**What I did with it.** The territory weight leans on workload (provider counts and the call plan), with patients as half of a blended weight, and the page says that prevalence is a size signal, not an intensity signal. Reporting a null result is the point of the check.

## 7. The registry ties out, to within one number

The monthly NPPES file has 357,925 records with no entity type; the separate deactivation report lists 357,926 numbers. All 357,925 are on the report, and the one extra is an active individual, who is removed from every count. Two files from the same agency built on different days agreeing to one record is the evidence that the filters mean what they say (check C03).

## 8. The baseline, and why it is a straw man on purpose

The comparison alignment gives every county the same weight, which is what drawing territories by county count amounts to. It shows what workload-aware weights buy (274% spread against 7.5%); it is not any company's alignment. A fairer internal comparison is the same method before and after the local search (diabetes 22.5% to 7.5%).

## 9. Excel checked against Excel

The sizing model is not trusted because it looks right. A script drives Excel through six input scenarios (both franchises, changed capacity, changed call plans) and a separate Python script, sharing no code with the workbook builder, recomputes 2,730 cells. A bug in the tooling rather than the workbook: PowerShell variable names are case-insensitive, so a typed `$Scenarios` path parameter swallowed a parsed `$scenarios` list.
