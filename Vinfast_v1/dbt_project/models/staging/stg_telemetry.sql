{{ config(materialized='view') }}

-- Staging telemetry: đọc Silver Parquet trực tiếp từ MinIO (lakehouse path,
-- không qua bảng raw_* trung gian trong ClickHouse).
-- Biểu thức glob */data.parquet phủ mọi phân vùng ngày (batch_date key).
select
    vehicle_id,
    event_timestamp,
    model,
    type,
    battery_soc_pct,
    battery_soh_pct,
    battery_temp_c,
    battery_temp_avg_c,
    battery_temp_max_c,
    charging_status,
    speed_kmh,
    odometer_km,
    motor_rpm,
    motor_temp_c,
    inverter_temp_c,
    gear_mode,
    latitude,
    longitude,
    acceleration_x,
    acceleration_y,
    acceleration_z,
    lock_status,
    cabin_temp_c,
    hvac_power_kw,
    airbag_deployed,
    tire_pressure_fl_bar,
    tire_pressure_fr_bar,
    tire_pressure_rl_bar,
    tire_pressure_rr_bar,
    tire_pressure_min_bar,
    ambient_temp_c,
    is_charging,
    charging_power_kw,
    ignition_on,
    is_driving,
    is_idle,
    tire_pressure_alert,
    battery_temp_alert,
    high_speed_event,
    hard_brake_event,
    -- derived: true driving event (not idle, not charging)
    (is_driving AND NOT is_charging) as is_driving_event
from s3('http://minio:9000/vinfast-silver/telemetry/*/data.parquet', 'vinfast', 'vinfast123', 'Parquet', 'vehicle_id String, event_timestamp DateTime64(3), model String, type String, battery_soc_pct Float64, battery_soh_pct Float64, battery_temp_c Float64, battery_temp_avg_c Float64, battery_temp_max_c Float64, charging_status String, speed_kmh Float64, odometer_km Float64, motor_rpm Int32, motor_temp_c Float64, inverter_temp_c Float64, gear_mode String, latitude Float64, longitude Float64, acceleration_x Float64, acceleration_y Float64, acceleration_z Float64, lock_status String, cabin_temp_c Nullable(Float64), hvac_power_kw Float64, airbag_deployed Bool, tire_pressure_fl_bar Nullable(Float64), tire_pressure_fr_bar Nullable(Float64), tire_pressure_rl_bar Nullable(Float64), tire_pressure_rr_bar Nullable(Float64), ambient_temp_c Float64, is_charging Bool, charging_power_kw Float64, ignition_on Bool, is_driving Bool, is_idle Bool, tire_pressure_min_bar Nullable(Float64), tire_pressure_alert Bool, battery_temp_alert Bool, high_speed_event Bool, hard_brake_event Bool, year Nullable(Int32), month Nullable(Int32), day Nullable(Int32)')
where vehicle_id IS NOT NULL
  and event_timestamp IS NOT NULL
