{{ config(materialized='table') }}

select
    station_id,
    charger_type,
    count(*) as session_count,
    sum(kwh_delivered) as total_kwh,
    sum(cost_vnd) as total_revenue_vnd,
    avg(kwh_delivered) as avg_kwh
from {{ ref('stg_charging_ext') }}
group by station_id, charger_type
