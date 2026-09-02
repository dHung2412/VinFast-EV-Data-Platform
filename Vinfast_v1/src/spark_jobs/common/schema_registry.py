from __future__ import annotations

from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# Lược đồ chuẩn cho dữ liệu chuỗi thời gian Telemetry
TELEMETRY_SCHEMA = StructType(
    [
        StructField("vehicle_id", StringType(), False),
        StructField("event_timestamp", TimestampType(), False),
        StructField("model", StringType(), True),
        StructField("type", StringType(), True),
        StructField("battery_soc_pct", DoubleType(), True),
        StructField("battery_soh_pct", DoubleType(), True),
        StructField("battery_temp_c", DoubleType(), True),
        StructField("battery_temp_avg_c", DoubleType(), True),
        StructField("battery_temp_max_c", DoubleType(), True),
        StructField("charging_status", StringType(), True),
        StructField("speed_kmh", DoubleType(), True),
        StructField("odometer_km", DoubleType(), True),
        StructField("motor_rpm", LongType(), True),
        StructField("motor_temp_c", DoubleType(), True),
        StructField("inverter_temp_c", DoubleType(), True),
        StructField("gear_mode", StringType(), True),
        StructField("latitude", DoubleType(), True),
        StructField("longitude", DoubleType(), True),
        StructField("acceleration_x", DoubleType(), True),
        StructField("acceleration_y", DoubleType(), True),
        StructField("acceleration_z", DoubleType(), True),
        StructField("lock_status", StringType(), True),
        StructField("cabin_temp_c", DoubleType(), True),
        StructField("hvac_power_kw", DoubleType(), True),
        StructField("airbag_deployed", BooleanType(), True),
        StructField("tire_pressure_fl_bar", DoubleType(), True),
        StructField("tire_pressure_fr_bar", DoubleType(), True),
        StructField("tire_pressure_rl_bar", DoubleType(), True),
        StructField("tire_pressure_rr_bar", DoubleType(), True),
        StructField("ambient_temp_c", DoubleType(), True),
        StructField("is_charging", BooleanType(), True),
        StructField("charging_power_kw", DoubleType(), True),
        StructField("ignition_on", BooleanType(), True),
    ]
)

# Lược đồ chuẩn cho dữ liệu Phiên sạc pin (Charging Sessions)
CHARGING_SCHEMA = StructType(
    [
        StructField("session_id", StringType(), False),
        StructField("vehicle_id", StringType(), True),
        StructField("station_id", StringType(), True),
        StructField("charger_type", StringType(), True),
        StructField("power_kw", DoubleType(), True),
        StructField("started_at", TimestampType(), True),
        StructField("ended_at", TimestampType(), True),
        StructField("duration_min", DoubleType(), True),
        StructField("kwh_delivered", DoubleType(), True),
        StructField("start_soc_pct", DoubleType(), True),
        StructField("end_soc_pct", DoubleType(), True),
        StructField("cost_vnd", DoubleType(), True),
        StructField("payment_method", StringType(), True),
    ]
)

# Lược đồ chuẩn cho dữ liệu Người dùng ứng dụng (Users)
USERS_SCHEMA = StructType(
    [
        StructField("u_id", StringType(), False),
        StructField("name", StringType(), True),
        StructField("phone", StringType(), True),
    ]
)

# Lược đồ chuẩn cho dữ liệu Phương tiện (Vehicles)
VEHICLES_SCHEMA = StructType(
    [
        StructField("vehicle_id", StringType(), False),
        StructField("u_id", StringType(), True),
        StructField("name", StringType(), True),
        StructField("model", StringType(), True),
        StructField("type", StringType(), True),
        StructField("city_code", StringType(), True),
        StructField("home_lat", DoubleType(), True),
        StructField("home_lon", DoubleType(), True),
        StructField("work_lat", DoubleType(), True),
        StructField("work_lon", DoubleType(), True),
        StructField("battery_kwh", DoubleType(), True),
        StructField("wh_per_km", DoubleType(), True),
        StructField("mass_kg", DoubleType(), True),
        StructField("Cd", DoubleType(), True),
        StructField("A_frontal_m2", DoubleType(), True),
        StructField("r_wheel_m", DoubleType(), True),
        StructField("gear_ratio", DoubleType(), True),
        StructField("V_pack_nom_v", DoubleType(), True),
        StructField("R_int_base_ohm", DoubleType(), True),
        StructField("odometer_start_km", DoubleType(), True),
        StructField("tire_pressure_base_bar", DoubleType(), True),
        StructField("battery_soh_pct", DoubleType(), True),
        StructField("years_old", DoubleType(), True),
    ]
)

# Lược đồ chuẩn cho dữ liệu Trạm sạc (Stations)
STATIONS_SCHEMA = StructType(
    [
        StructField("station_id", StringType(), False),
        StructField("city_code", StringType(), True),
        StructField("charger_type", StringType(), True),
        StructField("max_power_kw", DoubleType(), True),
        StructField("num_chargers", IntegerType(), True),
        StructField("lat", DoubleType(), True),
        StructField("lon", DoubleType(), True),
    ]
)
