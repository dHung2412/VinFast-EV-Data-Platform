{{ config(materialized='view') }}

-- Staging vehicles: đọc snapshot dimension từ MinIO Silver (entities pipeline),
-- join users để lấy thông tin chủ sở hữu. Các chỉ số thống kê vận hành
-- (total_events, avg_soc_pct, ...) không lưu trong dimension mà tính
-- trực tiếp từ stg_telemetry ở tầng intermediate/marts.
select
    v.vehicle_id,
    v.u_id,
    v.model,
    v.type,
    v.city_code,
    v.battery_kwh,
    v.battery_soh_pct,
    v.odometer_start_km,
    v.years_old,
    v.home_lat,
    v.home_lon,
    v.work_lat,
    v.work_lon,
    u.name as owner_name,
    u.phone as owner_phone
from s3('http://minio:9000/vinfast-silver/entities/vehicles/data.parquet', 'vinfast', 'vinfast123', 'Parquet', 'vehicle_id String, u_id String, model String, type String, city_code String, home_lat Float64, home_lon Float64, work_lat Float64, work_lon Float64, battery_kwh Float64, odometer_start_km Float64, tire_pressure_base_bar Float64, battery_soh_pct Float64, years_old Float64') as v
left join s3('http://minio:9000/vinfast-silver/entities/users/data.parquet', 'vinfast', 'vinfast123', 'Parquet', 'u_id String, name String, phone String') as u
    on v.u_id = u.u_id
where v.vehicle_id IS NOT NULL
