{{ config(materialized='table') }}

select
    s.session_id as session_id,
    s.vehicle_id as vehicle_id,
    v.model as model,
    v.city_code as city_code,
    s.station_id as station_id,
    s.charger_type as charger_type,
    s.started_at as started_at,
    s.ended_at as ended_at,
    s.duration_min as duration_min,
    s.duration_hours as duration_hours,
    s.kwh_delivered as kwh_delivered,
    s.start_soc_pct as start_soc_pct,
    s.end_soc_pct as end_soc_pct,
    s.cost_vnd as cost_vnd,
    s.payment_method as payment_method,
    s.is_fast_charge as is_fast_charge,
    s.avg_power_kw as avg_power_kw,
    s.cost_per_kwh_vnd as cost_per_kwh_vnd,
    s.charge_efficiency_pct as charge_efficiency_pct
from {{ ref('stg_charging_sessions') }} as s
left join {{ ref('stg_vehicles') }} as v
    on s.vehicle_id = v.vehicle_id
