{{ config(materialized='table') }}

with daily as (
    select * from {{ ref('int_vehicle_daily_stats') }}
),
trips as (
    select
        toDate(started_at) as activity_date,
        count(*) as total_trips,
        sum(distance_km) as total_distance_km
    from {{ ref('int_trip_segments') }}
    group by activity_date
),
charging as (
    select
        toDate(started_at) as activity_date,
        count(*) as total_charging_sessions,
        sum(kwh_delivered) as total_kwh_charged
    from {{ ref('stg_charging_sessions') }}
    group by activity_date
)
select
    d.activity_date as activity_date,
    countDistinct(d.vehicle_id) as active_vehicles,
    coalesce(t.total_trips, 0) as total_trips,
    coalesce(t.total_distance_km, 0) as total_distance_km,
    avg(d.avg_soc_pct) as avg_fleet_soc_pct,
    coalesce(c.total_charging_sessions, 0) as total_charging_sessions,
    coalesce(c.total_kwh_charged, 0) as total_kwh_charged,
    countIf(d.had_tire_pressure_alert = 1) as vehicles_with_tire_alert,
    countIf(d.had_battery_temp_alert = 1) as vehicles_with_temp_alert
from daily as d
left join trips as t on d.activity_date = t.activity_date
left join charging as c on d.activity_date = c.activity_date
group by d.activity_date, t.total_trips, t.total_distance_km, c.total_charging_sessions, c.total_kwh_charged
order by d.activity_date
