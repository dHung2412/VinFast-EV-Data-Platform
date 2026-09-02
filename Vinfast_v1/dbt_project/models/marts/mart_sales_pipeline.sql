{{ config(materialized='table') }}

select
    d.dealer_id,
    d.name as dealer_name,
    d.city_code,
    d.type as dealer_type,
    count(s.order_id) as order_count,
    countIf(s.model in ('VF3','VF5','VFe34','VF6','VF7','VF8','VF9')) as car_orders,
    countIf(s.model like 'VF_%') as bike_orders,
    sum(s.price_vnd) as total_revenue_vnd,
    avg(s.price_vnd) as avg_order_value_vnd,
    min(s.sold_at) as first_sale_at,
    max(s.sold_at) as last_sale_at
from {{ ref('stg_dms_dealers') }} d
left join {{ ref('stg_dms_sales_orders') }} s on d.dealer_id = s.dealer_id
group by d.dealer_id, d.name, d.city_code, d.type
order by total_revenue_vnd desc
