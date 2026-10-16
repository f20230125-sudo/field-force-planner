-- Marts: small tables the sizing and alignment code, the workbook and the dashboard read.

-- Counties that can be aligned: the 50 states and DC (Puerto Rico and the island areas are in the adjacency file but
-- not in the population, provider or prevalence sources used here).
create or replace table mart_county as
select c.county, c.state, c.name, c.land_sqmi, c.lat, c.lon, c.pop, c.adults, c.age65, c.franchise, c.prevalence,
       c.prevalence_imputed, c.patients
from dim_county c
order by c.county, c.franchise;

-- Providers by county and segment, with the call plan attached. Counties with no provider in a segment have no row;
-- the sizing code treats that as zero.
create or replace table mart_county_segment as
select f.county, c.state, f.franchise, f.segment, f.tier, f.hcps, s.calls_per_year, s.targeted_share
from fact_hcp_county f
join (select distinct county, state from dim_county) c using (county)
join (select distinct franchise, segment, calls_per_year, targeted_share from ref_segments) s using (franchise, segment)
order by f.county, f.franchise, f.segment;

-- Undirected county adjacency, each pair once.
create or replace table mart_edges as
select distinct least(a.county, a.neighbour) as a, greatest(a.county, a.neighbour) as b
from stg_adjacency a
where a.county in (select county from dim_county) and a.neighbour in (select county from dim_county)
order by 1, 2;

-- State roll-up for the Excel sizing model (one row per state and segment).
create or replace table mart_state_segment as
select state, franchise, segment, tier, sum(hcps) as hcps, any_value(calls_per_year) as calls_per_year,
       any_value(targeted_share) as targeted_share
from mart_county_segment group by state, franchise, segment, tier
order by state, franchise, segment;

create or replace table mart_state as
select state, franchise, sum(pop) as pop, sum(adults) as adults, sum(patients) as patients,
       count(*) as counties
from mart_county group by state, franchise
order by state, franchise;

copy mart_county         to '{marts_dir}/county.csv'         (header, delimiter ',');
copy mart_county_segment to '{marts_dir}/county_segment.csv' (header, delimiter ',');
copy mart_edges          to '{marts_dir}/edges.csv'          (header, delimiter ',');
copy mart_state_segment  to '{marts_dir}/state_segment.csv'  (header, delimiter ',');
copy mart_state          to '{marts_dir}/state.csv'          (header, delimiter ',');
