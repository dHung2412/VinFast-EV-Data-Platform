{{ config(materialized='table') }}

with customers as (
    select * from {{ ref('stg_crm_customers') }}
),
interactions_agg as (
    select
        customer_id,
        count(*) as interaction_count,
        max(occurred_at) as last_interaction_at,
        countIf(type = 'test_drive') as test_drive_count
    from {{ ref('stg_crm_interactions') }}
    group by customer_id
),
orders as (
    select
        phone,
        count(*) as order_count,
        sum(price_vnd) as total_spent_vnd,
        max(sold_at) as last_purchase_at
    from {{ ref('stg_dms_sales_orders') }}
    group by phone
)

select
    c.customer_id as customer_id,
    c.phone as phone,
    c.name as name,
    c.email as email,
    c.status as status,
    c.city_code as city_code,
    c.registered_at as registered_at,
    coalesce(i.interaction_count, 0) as interaction_count,
    i.last_interaction_at,
    i.test_drive_count,
    coalesce(o.order_count, 0) as order_count,
    o.total_spent_vnd,
    o.last_purchase_at,
    case
        when o.order_count > 0 then 'customer'
        when coalesce(i.test_drive_count, 0) > 0 then 'prospect_hot'
        when coalesce(i.interaction_count, 0) > 2 then 'prospect_warm'
        else 'lead'
    end as lifecycle_stage
from customers c
left join interactions_agg i on c.customer_id = i.customer_id
left join orders o on c.phone = o.phone
