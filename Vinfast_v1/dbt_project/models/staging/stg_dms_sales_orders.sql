{{ config(materialized='view') }}

select
    order_id,
    vin,
    vehicle_id,
    dealer_id,
    phone,
    sold_at,
    model,
    color,
    price_vnd,
    payment_method,
    warranty_start
from s3('http://minio:9000/vinfast-silver/dms/sales_order/*/data.parquet', 'vinfast', 'vinfast123', 'Parquet',
    'order_id String, vin String, vehicle_id Nullable(String), dealer_id String, phone String, sold_at String, model String, color String, price_vnd Float64, payment_method String, warranty_start String')
