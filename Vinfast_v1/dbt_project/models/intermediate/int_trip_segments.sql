{{ config(materialized='table') }}

-- Detect trips via gap > 300s (5 min) using ClickHouse window functions
-- Filter: max(speed) > 5 and duration >= 120s

with ordered as (
    select
        vehicle_id,
        event_timestamp,
        speed_kmh,
        odometer_km,
        battery_soc_pct,
        latitude,
        longitude,
        lagInFrame(event_timestamp) over (partition by vehicle_id order by event_timestamp) as prev_ts,
        lagInFrame(odometer_km) over (partition by vehicle_id order by event_timestamp) as prev_odo
    from {{ ref('stg_telemetry') }}
    where is_driving = true
),
with_gap as (
    select
        *,
        if(dateDiff('second', prev_ts, event_timestamp) > 300, 1, 0) as is_new_trip
    from ordered
),
with_trip_id as (
    select
        *,
        sum(is_new_trip) over (partition by vehicle_id order by event_timestamp rows between unbounded preceding and current row) as trip_seq
    from with_gap
),
grouped as (
    select
        vehicle_id,
        trip_seq,
        min(event_timestamp) as started_at,
        max(event_timestamp) as ended_at,
        dateDiff('second', min(event_timestamp), max(event_timestamp)) as duration_sec,
        count(*) as event_count,
        max(speed_kmh) as max_speed_kmh,
        avgIf(speed_kmh, speed_kmh > 2) as avg_moving_speed_kmh,
        min(odometer_km) as odo_start,
        max(odometer_km) as odo_end,
        min(battery_soc_pct) as soc_min,
        max(battery_soc_pct) as soc_max,
        -- SoC at start/end using argMin/argMax (ClickHouse cannot nest aggregates)
        argMin(battery_soc_pct, event_timestamp) as soc_start_pct,
        argMax(battery_soc_pct, event_timestamp) as soc_end_pct,
        argMin(latitude, event_timestamp) as start_lat,
        argMin(longitude, event_timestamp) as start_lon,
        argMax(latitude, event_timestamp) as end_lat,
        argMax(longitude, event_timestamp) as end_lon
    from with_trip_id
    group by vehicle_id, trip_seq
)
select
    concat(vehicle_id, '-', toString(started_at)) as trip_id,
    vehicle_id,
    started_at,
    ended_at,
    duration_sec / 60.0 as duration_min,
    odo_end - odo_start as distance_km,
    max_speed_kmh,
    avg_moving_speed_kmh,
    soc_start_pct,
    soc_end_pct,
    soc_start_pct - soc_end_pct as soc_drop_pct,
    start_lat,
    start_lon,
    end_lat,
    end_lon
from grouped
where max_speed_kmh > 5
  and duration_sec >= 120
