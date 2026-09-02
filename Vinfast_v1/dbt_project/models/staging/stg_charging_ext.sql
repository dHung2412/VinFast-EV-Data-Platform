{{ config(materialized='view') }}

select
    session_id,
    vin,
    vehicle_id,
    station_id,
    connector_id,
    charger_type,
    started_at,
    ended_at,
    kwh_delivered,
    cost_vnd,
    payment_method,
    duration_min,
    duration_hours,
    avg_power_kw,
    cost_per_kwh_vnd,
    is_fast_charge,
    source
from s3('http://minio:9000/vinfast-silver/charging_ext/*/data.parquet', 'vinfast', 'vinfast123', 'Parquet',
    'session_id String, vin Nullable(String), vehicle_id Nullable(String), station_id String, connector_id String, charger_type String, started_at DateTime64(3), ended_at DateTime64(3), kwh_delivered Float64, cost_vnd Int64, payment_method String, duration_min Float64, duration_hours Float64, avg_power_kw Nullable(Float64), cost_per_kwh_vnd Nullable(Float64), is_fast_charge Bool, source String, year Nullable(Int32), month Nullable(Int32), day Nullable(Int32)')
