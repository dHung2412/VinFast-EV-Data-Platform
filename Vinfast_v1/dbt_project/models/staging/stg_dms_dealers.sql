{{ config(materialized='view') }}

select
    dealer_id,
    name,
    nullIf(city_code, '') as city_code,
    address,
    lat,
    lon,
    type
from s3('http://minio:9000/vinfast-silver/dms/dealer/*/data.parquet', 'vinfast', 'vinfast123', 'Parquet',
    'dealer_id String, name String, city_code String, address String, lat Float64, lon Float64, type String, year Nullable(Int32), month Nullable(Int32)')
