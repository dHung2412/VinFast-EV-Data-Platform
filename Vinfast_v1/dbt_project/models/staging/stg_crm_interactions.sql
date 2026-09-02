{{ config(materialized='view') }}

select
    interaction_id,
    phone,
    customer_id,
    type,
    occurred_at,
    outcome,
    agent,
    notes
from s3('http://minio:9000/vinfast-silver/crm/interaction/*/data.parquet', 'vinfast', 'vinfast123', 'Parquet',
    'interaction_id String, phone String, customer_id String, type String, occurred_at DateTime64(3), outcome String, agent String, notes String, year Nullable(Int32), month Nullable(Int32)')
