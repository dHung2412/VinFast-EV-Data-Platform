{{ config(materialized='table') }}

with daily as (
    select * from {{ ref('int_vehicle_daily_stats') }}
),
charging as (
    select
        vehicle_id,
        count(*) as total_charging_sessions,
        sum(kwh_delivered) as total_kwh_charged
    from {{ ref('stg_charging_sessions') }}
    group by vehicle_id
),
telemetry_agg as (
    select
        vehicle_id,
        max(odometer_km) as latest_odometer_km,
        min(odometer_km) as earliest_odometer_km,
        avg(battery_soc_pct) as lifetime_avg_soc_pct,
        min(event_timestamp) as first_seen,
        max(event_timestamp) as last_seen
    from {{ ref('stg_telemetry') }}
    group by vehicle_id
)
select
    v.vehicle_id as vehicle_id,
    v.model as model,
    v.type as type,
    v.city_code as city_code,
    v.battery_kwh as battery_kwh,
    v.battery_soh_pct as current_soh_pct,
    coalesce(t.latest_odometer_km - v.odometer_start_km, 0) as total_distance_km,
    any(t.lifetime_avg_soc_pct) as lifetime_avg_soc_pct,
    coalesce(any(c.total_charging_sessions), 0) as total_charging_sessions,
    coalesce(any(c.total_kwh_charged), 0) as total_kwh_charged,
    max(d.had_tire_pressure_alert) as had_tire_pressure_alert,
    max(d.had_battery_temp_alert) as had_battery_temp_alert,
    countDistinct(d.activity_date) as total_active_days,
    toDate(any(t.first_seen)) as first_seen_date,
    toDate(any(t.last_seen)) as last_seen_date
from {{ ref('stg_vehicles') }} as v
left join telemetry_agg as t on v.vehicle_id = t.vehicle_id
left join daily as d on v.vehicle_id = d.vehicle_id
left join charging as c on v.vehicle_id = c.vehicle_id
group by
    v.vehicle_id, v.model, v.type, v.city_code, v.battery_kwh, v.battery_soh_pct,
    v.odometer_start_km, t.latest_odometer_km
