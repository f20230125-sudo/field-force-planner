-- Staging: every source as published, typed where the type is certain, nothing removed.

create or replace table stg_nppes as
select npi, entity_type, credential, city, state, postal, country,
       try_strptime(enumerated, '%m/%d/%Y')::date as enumerated,
       try_strptime(last_update, '%m/%d/%Y')::date as last_update,
       deact_reason,
       try_strptime(deact_date, '%m/%d/%Y')::date as deact_date,
       try_strptime(react_date, '%m/%d/%Y')::date as react_date,
       tax1, tax2, tax3, tax4, tax5, tax6, tax7, tax8, tax9, tax10, tax11, tax12, tax13, tax14, tax15,
       sw1, sw2, sw3, sw4, sw5, sw6, sw7, sw8, sw9, sw10, sw11, sw12, sw13, sw14, sw15
from read_parquet('{nppes}');

create or replace table stg_deactivated as
select npi, try_strptime(deact_date, '%m/%d/%Y')::date as deact_date from read_parquet('{deact}');

create or replace table stg_nucc as
select "Code" as code, "Grouping" as grouping, "Classification" as classification, "Specialization" as specialization,
       "Display Name" as display_name
from read_csv('{nucc}', header = true, all_varchar = true);

-- Census 2020 ZIP-code-tabulation-area to county overlaps: one row per (ZCTA, county) pair, with the land area of the overlap.
create or replace table stg_zcta_county as
select GEOID_ZCTA5_20 as zcta, GEOID_COUNTY_20 as county, try_cast(AREALAND_PART as double) as land_part
from read_csv('{zcta}', delim = '|', header = true, all_varchar = true)
where GEOID_ZCTA5_20 is not null and GEOID_ZCTA5_20 <> '';

-- The Gazetteer's last header carries trailing spaces, so the names are given explicitly.
create or replace table stg_gazetteer as
select geoid as county, usps as state, name, try_cast(aland_sqmi as double) as land_sqmi,
       try_cast(trim(intptlat) as double) as lat, try_cast(trim(intptlong) as double) as lon
from read_csv('{gazetteer}', delim = '\t', header = true, all_varchar = true,
              names = ['usps', 'geoid', 'ansicode', 'name', 'aland', 'awater', 'aland_sqmi', 'awater_sqmi',
                       'intptlat', 'intptlong']);

-- CDC PLACES county estimates: the 2023 release (survey year 2021), plus Florida from the 2024 release (survey year 2022)
-- because Florida has no 2021 data.
create or replace table stg_places as
select year::integer as year, stateabbr as state, locationname as name, locationid as county, measureid,
       try_cast(data_value as double) / 100 as prevalence,
       try_cast(low_confidence_limit as double) / 100 as low, try_cast(high_confidence_limit as double) / 100 as high,
       try_cast(totalpopulation as bigint) as places_population, 'PLACES 2023' as release
from read_csv('{places}', header = true, all_varchar = true)
union all
select year::integer, stateabbr, locationname, locationid, measureid,
       try_cast(data_value as double) / 100, try_cast(low_confidence_limit as double) / 100,
       try_cast(high_confidence_limit as double) / 100, try_cast(totalpopulation as bigint), 'PLACES 2024 (Florida)'
from read_csv('{places_fl}', header = true, all_varchar = true);

create or replace table stg_popest as
select lpad(STATE, 2, '0') || lpad(COUNTY, 3, '0') as county, STNAME as state_name, CTYNAME as name,
       try_cast(POPESTIMATE as bigint) as pop, try_cast(AGE18PLUS_TOT as bigint) as adults,
       try_cast(AGE65PLUS_TOT as bigint) as age65
from read_csv('{popest}', header = true, all_varchar = true, encoding = 'latin-1')  -- the Census file is Latin-1 ("Doña Ana")
where YEAR = '3';
