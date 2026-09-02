{{ config(materialized='table') }}

select
    vehicle_id,
    toDate(event_timestamp) as activity_date,
    count(*) as event_count,
    avg(battery_soc_pct) as avg_soc_pct,
    max(speed_kmh) as max_speed_kmh,
    max(odometer_km) - min(odometer_km) as distance_km,
    countIf(is_charging) as charging_events_count,
    max(if(tire_pressure_alert, 1, 0)) as had_tire_pressure_alert,
    max(if(battery_temp_alert, 1, 0)) as had_battery_temp_alert,
    max(if(high_speed_event, 1, 0)) as had_high_speed_event,
    max(if(hard_brake_event, 1, 0)) as had_hard_brake_event
from {{ ref('stg_telemetry') }}
group by vehicle_id, activity_date
