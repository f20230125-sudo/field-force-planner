# Data-quality scorecard

25 checks run against the warehouse and the alignment. 18 pass, 0 warn, 0 fail, 7 are measurements with no rule.

Regenerate with `python -m ff.dq`. Failures and warnings come first.

## C01 Every registry record is an individual, an organisation or a deactivated number

- **Status:** pass
- **Result:** 9,852,180 records = 7,512,094 individuals + 1,982,161 organisations + 357,925 with no entity type
- **Rule:** the three add up
- **Note:** A deactivated NPI stays in the file with every field blank except the number.

## C02 Each NPI appears once and has ten digits

- **Status:** pass
- **Result:** 0 duplicates, 0 malformed
- **Rule:** 0 and 0

## C03 Deactivated numbers in the monthly file match the separate deactivation report

- **Status:** pass
- **Result:** 357,925 of 357,925 blank records are on the report (357,926 listed)
- **Rule:** all of them, and the report lists at most 10 more
- **Note:** Two files from the same agency, built on different days; agreement to within one number is the expectation.

## C06 Individuals with a primary taxonomy flagged

- **Status:** pass
- **Result:** 100.00%
- **Rule:** at least 99%
- **Note:** Where none is flagged the first listed taxonomy is used.

## C07 Every taxonomy code used for a segment exists in the NUCC code set

- **Status:** pass
- **Result:** 20 of 20
- **Rule:** all
- **Note:** Codes are NUCC 25.1.

## C08 Providers whose ZIP code is a readable five digits

- **Status:** pass
- **Result:** 100.00%
- **Rule:** at least 99%

## C09 Providers whose ZIP code reached a county

- **Status:** pass
- **Result:** 7,375,945 of 7,458,766 (98.89%)
- **Rule:** at least 97%
- **Note:** A ZIP code is not a Census ZCTA: PO-box and single-building ZIPs have no area. Unmatched providers are left out of county counts, so every county figure is a slight undercount.

## C10 Provider's state agrees with the state of the county their ZIP maps to

- **Status:** pass
- **Result:** 3,003 of 7,375,945 differ (0.041%)
- **Rule:** under 1%
- **Note:** A ZIP near a state line can map to the neighbouring state's county; the county wins.

## C12 Counties kept after joining the Gazetteer, population and prevalence sources

- **Status:** pass
- **Result:** 3,143 of 3,143 in the population file
- **Rule:** all
- **Note:** An earlier run used the 2023 Gazetteer, in which Connecticut has planning regions instead of counties, and silently lost 8 counties. The 2021 Gazetteer and the 2023 PLACES release use the old counties.

## C13 Counties with no CDC PLACES estimate (given their state's median)

- **Status:** pass
- **Result:** 0 of 3143 (0.0%)
- **Rule:** under 3%
- **Note:** The first run of this check found 67 counties, all of Florida: the 2023 PLACES release has no Florida data (the state did not release its 2021 survey). Florida now takes its 2022 estimates from the 2024 release. Any county still missing would get its state's median and be flagged in the county table.

## C14 Share of diabetes patients that sit in imputed counties

- **Status:** pass
- **Result:** 0.00%
- **Rule:** under 3%

## C15 County adjacency is symmetric (if A touches B, B touches A)

- **Status:** pass
- **Result:** 0 one-way pairs
- **Rule:** 0

## C17 Workload adds up the same by county, by state and by segment

- **Status:** pass
- **Result:** diabetes 1,990,916; oncology 359,910 calls a year
- **Rule:** equal to the call

## C18 Providers by county and segment add up to providers placed in a segment

- **Status:** pass
- **Result:** 952,577 vs 952,577
- **Rule:** equal

## C19a Diabetes: territories are connected, none empty, count equals reps

- **Status:** pass
- **Result:** 1310 territories, 0 disconnected, reps 1309.8
- **Rule:** 0 disconnected; count = round(reps)

## C19b Oncology: territories are connected, none empty, count equals reps

- **Status:** pass
- **Result:** 474 territories, 0 disconnected, reps 473.6
- **Rule:** 0 disconnected; count = round(reps)

## C20a Diabetes: territory workload within 25% of the target

- **Status:** pass
- **Result:** 99.6% of territories (within 10%: 72.9%); baseline 8.8%
- **Rule:** at least 95%
- **Note:** The baseline cuts the same number of territories with equal numbers of counties, blind to workload.

## C20b Oncology: territory workload within 25% of the target

- **Status:** pass
- **Result:** 99.6% of territories (within 10%: 88.4%); baseline 9.5%
- **Rule:** at least 95%
- **Note:** The baseline cuts the same number of territories with equal numbers of counties, blind to workload.

## C04 Individuals still listed as active that the deactivation report lists

- **Status:** info
- **Result:** 1
- **Rule:** excluded from the provider table
- **Note:** Removed from every count here, so a number cannot be both.

## C05 Individuals kept: active, in the 50 states and DC

- **Status:** info
- **Result:** 7,458,766 of 7,512,094 (99.3%)
- **Rule:** report
- **Note:** Outside this scope: foreign addresses, territories (Puerto Rico, Guam, ...), deactivated.

## C11 Providers in a ZIP area where one county holds at least 80% of the land

- **Status:** info
- **Result:** 94.5%
- **Rule:** report
- **Note:** Where a ZIP area spans counties the provider goes to the county with most of its land. That is right for most and wrong for some; city centres are better served by the dominant county than the rural remainder, which is why land share is a fair rule here.

## C16 Counties that touch no other county (islands)

- **Status:** info
- **Result:** 7
- **Rule:** report
- **Note:** Joined to the nearest mainland county by distance if within 300 km; Alaska and Hawaii are aligned separately.

## C21a Diabetes: counties split between territories

- **Status:** info
- **Result:** 865 of 3,143
- **Rule:** report
- **Note:** A county worth more than 0.15 territories is cut into equal pieces (ZIP-level bricks would do this properly).

## C21b Oncology: counties split between territories

- **Status:** info
- **Result:** 343 of 3,143
- **Rule:** report
- **Note:** A county worth more than 0.15 territories is cut into equal pieces (ZIP-level bricks would do this properly).

## C22 Prevalence-based demand against observed Medicaid drug spend, by state

- **Status:** info
- **Result:** diabetes: size rho 0.86, spend per enrollee rho -0.10; oncology: size rho 0.95, spend per enrollee rho -0.04
- **Rule:** report
- **Note:** Demand follows population (high rho) but prevalence does not explain Medicaid spend per enrollee (rho near 0): formulary, benefit design and who is enrolled dominate. Territory weights therefore balance workload first.
