-- Clean dimensions and facts.

-- Segment definitions from the committed reference files (data/ref/segments.csv, franchises.csv).
create or replace table ref_segments as
select franchise, segment, tier, calls_per_year::double as calls_per_year, targeted_share::double as targeted_share,
       taxonomy_code
from read_csv('{ref_dir}/segments.csv', header = true, all_varchar = true);

create or replace table ref_franchises as
select franchise, label, places_measure, calls_per_rep_day::double as calls_per_rep_day, field_days::double as field_days,
       patient_label
from read_csv('{ref_dir}/franchises.csv', header = true, all_varchar = true);

-- ---------------------------------------------------------------- counties
-- One row per 2020 county: population (Census estimate, July 2021), adults, and the CDC PLACES prevalence for each
-- franchise's measure. A county PLACES does not publish gets its state's median (then the national median) and says so.
create or replace table dim_county as
with prev as (
    select county, measureid, max(prevalence) as prevalence, any_value(year) as survey_year from stg_places group by 1, 2
),
base as (
    select g.county, g.state, g.name, g.land_sqmi, g.lat, g.lon, p.pop, p.adults, p.age65
    from stg_gazetteer g join stg_popest p using (county)
),
joined as (
    select b.*, f.franchise, f.places_measure, pv.prevalence, pv.survey_year
    from base b cross join ref_franchises f
    left join prev pv on pv.county = b.county and pv.measureid = f.places_measure
),
state_median as (
    select state, franchise, quantile_cont(prevalence, 0.5) as m from joined where prevalence is not null group by 1, 2
),
nat_median as (
    select franchise, quantile_cont(prevalence, 0.5) as m from joined where prevalence is not null group by 1
)
select j.county, j.state, j.name, j.land_sqmi, j.lat, j.lon, j.pop, j.adults, j.age65, j.franchise,
       coalesce(j.prevalence, s.m, n.m) as prevalence,
       j.prevalence is null as prevalence_imputed,
       j.survey_year as prevalence_year,
       round(j.adults * coalesce(j.prevalence, s.m, n.m)) as patients
from joined j
left join state_median s on s.state = j.state and s.franchise = j.franchise
left join nat_median n on n.franchise = j.franchise;

-- ---------------------------------------------------------------- ZIP to county
-- A ZIP code in the registry is matched to a Census ZCTA (the Census approximation of a ZIP area). Where a ZCTA spans
-- counties it goes to the county holding most of its land; share_in_county says how clear-cut that is.
create or replace table map_zip_county as
with ranked as (
    select zcta, county, land_part,
           row_number() over (partition by zcta order by land_part desc, county) as rk,
           sum(land_part) over (partition by zcta) as total
    from stg_zcta_county
)
select zcta, county, land_part / nullif(total, 0) as share_in_county from ranked where rk = 1;

-- ---------------------------------------------------------------- health-care providers
-- Individuals only, in the 50 states and DC, not on the deactivation report. The primary taxonomy (the one flagged
-- 'Y') decides the specialty; if none is flagged, the first listed is used.
create or replace table dim_hcp as
select npi,
       state,
       case when regexp_matches(postal, '^[0-9]{5}') then left(postal, 5) end as zip5,
       coalesce(case when sw1 = 'Y' then tax1 when sw2 = 'Y' then tax2 when sw3 = 'Y' then tax3 when sw4 = 'Y' then tax4
                     when sw5 = 'Y' then tax5 when sw6 = 'Y' then tax6 when sw7 = 'Y' then tax7 when sw8 = 'Y' then tax8
                     when sw9 = 'Y' then tax9 when sw10 = 'Y' then tax10 when sw11 = 'Y' then tax11
                     when sw12 = 'Y' then tax12 when sw13 = 'Y' then tax13 when sw14 = 'Y' then tax14
                     when sw15 = 'Y' then tax15 end, tax1) as primary_taxonomy,
       deact_date is not null as was_deactivated
from stg_nppes
where entity_type = '1' and country = 'US'
  and state in (select distinct state from dim_county)  -- the 50 states and DC (the Gazetteer also lists Puerto Rico)
  and npi not in (select npi from stg_deactivated);

create or replace table hcp_geo as
select h.npi, h.state as hcp_state, h.zip5, h.primary_taxonomy, m.county, d.state as county_state,
       m.share_in_county
from dim_hcp h
left join map_zip_county m on m.zcta = h.zip5
left join (select county, any_value(state) as state from dim_county group by 1) d on d.county = m.county;

create or replace table hcp_segment as
select g.*, s.franchise, s.segment, s.tier
from hcp_geo g
join (select distinct franchise, segment, tier, taxonomy_code from ref_segments) s on s.taxonomy_code = g.primary_taxonomy;

-- Providers per county and segment (only those whose ZIP reached a county).
create or replace table fact_hcp_county as
select county, franchise, segment, tier, count(*) as hcps
from hcp_segment where county is not null
group by all;
