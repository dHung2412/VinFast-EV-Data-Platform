{{ config(materialized='view') }}

-- Staging charging sessions (mạng VinFast nội bộ, trích từ telemetry):
-- đọc Silver Parquet trực tiếp từ MinIO. Các cột phái sinh (avg_power_kw,
-- cost_per_kwh_vnd, is_fast_charge, charge_efficiency_pct) do plugin
-- charging_internal tính ở tầng Silver; tầng dbt chỉ giới hạn hiệu suất 0-200%.
select
    session_id,
    vehicle_id,
    station_id,
    charger_type,
    power_kw,
    started_at,
    ended_at,
    duration_min,
    duration_min / 60.0 as duration_hours,
    kwh_delivered,
    start_soc_pct,
    end_soc_pct,
    cost_vnd,
    payment_method,
    avg_power_kw,
    cost_per_kwh_vnd,
    is_fast_charge,
    least(greatest(charge_efficiency_pct, 0), 200) as charge_efficiency_pct
from s3('http://minio:9000/vinfast-silver/charging_internal/*/data.parquet', 'vinfast', 'vinfast123', 'Parquet', 'session_id String, vehicle_id String, station_id String, charger_type String, power_kw Nullable(Float64), started_at DateTime64(3), ended_at DateTime64(3), duration_min Float64, kwh_delivered Float64, start_soc_pct Nullable(Float64), end_soc_pct Nullable(Float64), cost_vnd Int64, payment_method String, battery_kwh Nullable(Float64), duration_hours Nullable(Float64), avg_power_kw Nullable(Float64), cost_per_kwh_vnd Nullable(Float64), is_fast_charge Bool, charge_efficiency_pct Nullable(Float64), year Nullable(Int32), month Nullable(Int32), day Nullable(Int32)')
where session_id IS NOT NULL
  and vehicle_id IS NOT NULL
  and started_at IS NOT NULL
  and ended_at IS NOT NULL
