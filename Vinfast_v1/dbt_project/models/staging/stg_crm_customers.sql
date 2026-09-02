{{ config(materialized='view') }}

-- Staging CRM customers: reads Silver parquet from MinIO via s3() glob for date partitions (excludes stale no-date key)
select
    customer_id,
    phone,
    name,
    email,
    status,
    nullIf(city_code, '') as city_code,
    registered_at,
    crm_customer_code
from s3('http://minio:9000/vinfast-silver/crm/customer/*/data.parquet', 'vinfast', 'vinfast123', 'Parquet',
    'customer_id String, phone String, name String, email Nullable(String), status String, city_code String, registered_at DateTime64(3), crm_customer_code String, year Nullable(Int32), month Nullable(Int32)')
