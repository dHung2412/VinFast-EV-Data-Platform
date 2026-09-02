from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.data_generator.telemetry.entities import AMBIENT_BY_CITY, CITIES
from src.data_generator.telemetry.telemetry_sim import (
    MINUTES_PER_DAY,
    SAMPLE_SECONDS_CHARGING,
    SAMPLE_SECONDS_DRIVING,
    TIRE_POSITIONS,
    ambient_curve,
    build_frame,
    empty_activity,
    simulate_charge,
    simulate_trip,
)
from src.data_generator.utils import make_rng

# Múi giờ địa phương và múi giờ chuẩn quốc tế
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC = timezone.utc

# Danh sách các cột thuộc lược đồ dữ liệu Telemetry chuẩn đầu ra
COLUMNS = [
    "vehicle_id",
    "event_timestamp",
    "model",
    "type",
    # Thông số Pin
    "battery_soc_pct",
    "battery_soh_pct",
    "battery_temp_c",
    "battery_temp_avg_c",
    "battery_temp_max_c",
    "charging_status",
    # Hệ thống truyền động & Vận hành
    "speed_kmh",
    "odometer_km",
    "motor_rpm",
    "motor_temp_c",
    "inverter_temp_c",
    "gear_mode",
    # Định vị GNSS & Cảm biến quán tính IMU
    "latitude",
    "longitude",
    "acceleration_x",
    "acceleration_y",
    "acceleration_z",
    # Thân xe & An toàn
    "lock_status",
    "cabin_temp_c",
    "hvac_power_kw",
    "airbag_deployed",
    # Khung gầm & Môi trường
    "tire_pressure_fl_bar",
    "tire_pressure_fr_bar",
    "tire_pressure_rl_bar",
    "tire_pressure_rr_bar",
    "ambient_temp_c",
    "is_charging",
    "charging_power_kw",
    "ignition_on",
]


def generate_telemetry_day(fleet: list[dict], day: date, seed: int) -> pd.DataFrame:
    """Tạo dữ liệu chuỗi thời gian telemetry cho toàn bộ đội xe trong một ngày chỉ định."""
    day_start = datetime(day.year, day.month, day.day)
    frames = []

    for vehicle in fleet:
        rng = make_rng(seed, "telemetry", vehicle["vehicle_id"], day.isoformat())
        frames.append(_simulate_vehicle_day(rng, vehicle, day_start))

    if not frames:
        return pd.DataFrame(columns=COLUMNS)

    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)

    # Sắp xếp dữ liệu theo mã xe và mốc thời gian giây trong ngày
    sort_col = "_off_seconds" if "_off_seconds" in df.columns else "_off_min"
    df = df.sort_values(["vehicle_id", sort_col], kind="stable").reset_index(drop=True)

    return _finalize(df)


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa cột mốc thời gian event_timestamp (UTC), gán kiểu dữ liệu và lọc đúng thứ tự các cột."""
    midnight = np.datetime64(df["day_start"].iloc[0])
    if "_off_seconds" in df.columns:
        seconds = df["_off_seconds"].to_numpy(dtype="int64")
    else:
        seconds = df["_off_min"].to_numpy(dtype="int64") * 60

    ts_local = (midnight + seconds.astype("timedelta64[s]")).astype("datetime64[ns]")
    ts_utc = pd.DatetimeIndex(ts_local).tz_localize(LOCAL_TZ).tz_convert(UTC)
    df["event_timestamp"] = ts_utc

    out = df.copy()
    for col in COLUMNS:
        if col not in out.columns:
            out[col] = np.nan

    out = out[COLUMNS].copy()
    out["speed_kmh"] = out["speed_kmh"].astype("float64")
    out["battery_soc_pct"] = out["battery_soc_pct"].astype("float64")
    out["battery_soh_pct"] = out["battery_soh_pct"].astype("float64")

    return out


def _simulate_vehicle_day(
    rng: np.random.Generator, vehicle: dict, day_start: datetime
) -> pd.DataFrame:
    """Mô phỏng toàn bộ hoạt động của một phương tiện trong 1 ngày (chuyến đi, sạc pin, đỗ xe)."""
    ambient_cfg = AMBIENT_BY_CITY[vehicle["city_code"]]
    is_weekend = day_start.weekday() >= 5

    # Số lượng chuyến đi trong ngày (cuối tuần vs ngày thường)
    trip_probs = [0.30, 0.45, 0.25] if is_weekend else [0.10, 0.55, 0.35]
    n_trips = int(rng.choice([1, 2, 3], p=trip_probs))

    if vehicle.get("type") == "motorbike" and rng.random() < 0.3:
        n_trips = max(1, n_trips - 1)

    soc = float(rng.uniform(45.0, 95.0))
    soh = float(vehicle.get("battery_soh_pct", 98.0))
    odometer = float(vehicle["odometer_start_km"])
    tire_base = float(vehicle["tire_pressure_base_bar"])

    # Mô phỏng rủi ro thủng lốp (2% xác suất)
    puncture_tire = TIRE_POSITIONS[int(rng.integers(4))] if rng.random() < 0.02 else None
    if vehicle.get("type") == "motorbike" and puncture_tire is not None:
        puncture_tire = str(rng.choice(["fl", "fr"]))

    location = {"lat": vehicle["home_lat"], "lon": vehicle["home_lon"]}
    segments: list[pd.DataFrame] = []
    cursor_sec = int(rng.integers(5 * 60, 9 * 60)) * 60
    day_start_iso = day_start.isoformat()
    airbag_triggered = False

    # 1. Mô phỏng các chuyến đi di chuyển trong ngày
    for trip_no in range(n_trips):
        if cursor_sec > (MINUTES_PER_DAY * 60 - 20 * 60):
            break

        is_bike = vehicle.get("type") == "motorbike"
        distance_km = (
            float(np.clip(rng.normal(10.0, 5.0), 3.0, 25.0))
            if is_bike
            else float(np.clip(rng.normal(18.0, 9.0), 4.0, 55.0))
        )

        if trip_no == 0 and not is_weekend:
            dest = {"lat": vehicle["work_lat"], "lon": vehicle["work_lon"]}
        else:
            dest = _pick_destination(rng, vehicle)

        if airbag_triggered:
            break

        trip = simulate_trip(
            rng,
            vehicle,
            day_start_iso,
            start_off_min=cursor_sec // 60,
            distance_km=distance_km,
            origin=location,
            dest=dest,
            soc=soc,
            soh=soh,
            odometer=odometer,
            tire_base=tire_base,
            puncture_tire=puncture_tire,
            ambient_mean=float(ambient_cfg["mean"]),
            ambient_amp=float(ambient_cfg["amp"]),
        )
        segments.append(trip["frame"])

        soc = trip["soc_end"]
        soh = trip["soh_end"]
        odometer = trip["odometer_end"]
        location = dest
        cursor_sec = trip["end_off_seconds"] + int(rng.integers(45 * 60, 200 * 60))

        # Kiểm tra sự kiện nổ túi khí ngắt chuyến đi
        if bool(trip["frame"]["airbag_deployed"].any()):
            airbag_triggered = True
            break

        # Cơ hội sạc pin ban ngày khi mức pin thấp (< 22%)
        if soc < 22.0 and rng.random() < 0.6 and cursor_sec < (MINUTES_PER_DAY * 60 - 30 * 60):
            pwr = float(rng.choice([2.0, 3.5])) if is_bike else float(rng.choice([120.0, 150.0]))
            ctype = "AC_TYPE2" if is_bike else "CCS2_DC"

            charge = simulate_charge(
                rng,
                vehicle,
                day_start_iso,
                start_off_min=cursor_sec // 60,
                soc_start=soc,
                soh=soh,
                target_soc=float(rng.uniform(75.0, 92.0)),
                power_kw=pwr,
                charger_type=ctype,
                odometer=odometer,
                tire_base=tire_base,
                lat=float(dest["lat"] + rng.normal(0, 0.01)),
                lon=float(dest["lon"] + rng.normal(0, 0.01)),
                ambient_mean=float(ambient_cfg["mean"]),
                ambient_amp=float(ambient_cfg["amp"]),
            )
            if charge is not None:
                segments.append(charge["frame"])
                soc = charge["soc_end"]
                soh = charge["soh_end"]
                cursor_sec = charge["end_off_seconds"] + int(rng.integers(5 * 60, 20 * 60))

    # 2. Mô phỏng sạc pin ban đêm tại nhà (khi soc < 88%)
    if not airbag_triggered:
        last_activity_sec = int(segments[-1]["_off_seconds"].max()) if segments else 0
        night_start_min = int(rng.integers(21 * 60, 23 * 60))
        night_start_sec = night_start_min * 60

        if soc < 88.0 and night_start_sec > last_activity_sec + 5 * 60:
            is_bike = vehicle.get("type") == "motorbike"
            pwr = float(rng.choice([1.5, 2.5])) if is_bike else 11.0
            ctype = "AC_TYPE2"

            charge = simulate_charge(
                rng,
                vehicle,
                day_start_iso,
                start_off_min=night_start_min,
                soc_start=max(soc, 8.0),
                soh=soh,
                target_soc=100.0,
                power_kw=pwr,
                charger_type=ctype,
                odometer=odometer,
                tire_base=tire_base,
                lat=float(vehicle["home_lat"]),
                lon=float(vehicle["home_lon"]),
                ambient_mean=float(ambient_cfg["mean"]),
                ambient_amp=float(ambient_cfg["amp"]),
            )
            if charge is not None:
                segments.append(charge["frame"])

    activity = (
        pd.concat(segments, ignore_index=True)
        if segments
        else empty_activity(day_start_iso, vehicle["vehicle_id"])
    )

    # 3. Sinh dữ liệu mẫu nhịp tim Heartbeat định kỳ mỗi 15 phút khi xe dừng đỗ
    heartbeats = _heartbeat_rows(activity, rng, vehicle, soc, soh, day_start_iso, ambient_cfg)
    combined = activity if len(heartbeats) == 0 else pd.concat([activity, heartbeats], ignore_index=True)

    return combined


def _pick_destination(rng: np.random.Generator, vehicle: dict) -> dict:
    """Chọn ngẫu nhiên điểm đến cho chuyến đi (nhà riêng, nơi làm việc, hoặc điểm POI)."""
    choice = str(rng.choice(["home", "work", "poi"], p=[0.4, 0.25, 0.35]))
    if choice == "home":
        return {"lat": vehicle["home_lat"], "lon": vehicle["home_lon"]}
    if choice == "work":
        return {"lat": vehicle["work_lat"], "lon": vehicle["work_lon"]}

    center = CITIES[vehicle["city_code"]]
    return {
        "lat": float(center["lat"] + rng.normal(0, 0.03)),
        "lon": float(center["lon"] + rng.normal(0, 0.03)),
    }


def _heartbeat_rows(
    activity: pd.DataFrame,
    rng: np.random.Generator,
    vehicle: dict,
    soc_default: float,
    soh_default: float,
    day_start_iso: str,
    ambient_cfg: dict,
) -> pd.DataFrame:
    """Sinh chuỗi dữ liệu nhịp tim Heartbeat định kỳ mỗi 15 phút khi xe ở trạng thái dừng đỗ (idle/parked)."""
    if len(activity) and "_off_seconds" in activity.columns:
        busy_secs = set((activity["_off_seconds"].to_numpy(dtype="int64") // 900).tolist())
    elif len(activity):
        busy_secs = set((activity["_off_min"].to_numpy(dtype="int64") * 60 // 900).tolist())
    else:
        busy_secs = set()

    all_slots = []
    for h in range(24):
        for m in [0, 15, 30, 45]:
            sec = h * 3600 + m * 60 + int(rng.integers(0, 30))
            bucket = sec // 900
            if bucket not in busy_secs:
                all_slots.append(sec)

    if not all_slots:
        return empty_activity(day_start_iso, vehicle["vehicle_id"])

    off_seconds = np.array(sorted(all_slots), dtype="int64")
    off_min = (off_seconds // 60).astype(np.int64)
    n = len(off_seconds)

    if len(activity):
        offsets = (
            activity["_off_seconds"].to_numpy(dtype="int64")
            if "_off_seconds" in activity.columns
            else activity["_off_min"].to_numpy(dtype="int64") * 60
        )
        order = np.argsort(offsets, kind="stable")
        sorted_offsets = offsets[order]
        sorted_activity = activity.iloc[order]
        positions = np.searchsorted(sorted_offsets, off_seconds, side="right") - 1

        cols = [
            "battery_soc_pct", "battery_soh_pct", "latitude", "longitude", "odometer_km",
            "battery_temp_c", "motor_temp_c", "inverter_temp_c"
        ]
        for c in cols:
            if c not in sorted_activity.columns:
                sorted_activity[c] = np.nan

        src = sorted_activity[cols]
        first_vals = src.iloc[0]
        pos_clipped = np.maximum(positions, 0)
        rows = src.iloc[pos_clipped].reset_index(drop=True)
        is_early = positions < 0

        soc_arr_src = rows["battery_soc_pct"].to_numpy(dtype=float)
        soh_arr_src = rows["battery_soh_pct"].to_numpy(dtype=float)

        soc = np.where(is_early, float(first_vals["battery_soc_pct"]) if not pd.isna(first_vals["battery_soc_pct"]) else soc_default, soc_arr_src)
        soh = np.where(is_early, float(first_vals["battery_soh_pct"]) if not pd.isna(first_vals["battery_soh_pct"]) else soh_default, soh_arr_src)

        lat = np.where(is_early, float(first_vals["latitude"]) if not pd.isna(first_vals["latitude"]) else vehicle["home_lat"], rows["latitude"].to_numpy(dtype=float))
        lon = np.where(is_early, float(first_vals["longitude"]) if not pd.isna(first_vals["longitude"]) else vehicle["home_lon"], rows["longitude"].to_numpy(dtype=float))

        odo_first = float(first_vals["odometer_km"]) if not pd.isna(first_vals["odometer_km"]) else vehicle["odometer_start_km"]
        odo = np.where(is_early, odo_first, rows["odometer_km"].to_numpy(dtype=float))

        mean = float(ambient_cfg["mean"])
        batt_first = float(first_vals["battery_temp_c"]) if not pd.isna(first_vals["battery_temp_c"]) else mean + 6.0
        motor_first = float(first_vals["motor_temp_c"]) if not pd.isna(first_vals["motor_temp_c"]) else mean + 8.0
        inv_first = float(first_vals["inverter_temp_c"]) if not pd.isna(first_vals["inverter_temp_c"]) else mean + 5.0

        batt_temp = np.where(is_early, batt_first, rows["battery_temp_c"].to_numpy(dtype=float))
        motor_temp = np.where(is_early, motor_first, rows["motor_temp_c"].to_numpy(dtype=float))
        inv_temp = np.where(is_early, inv_first, rows["inverter_temp_c"].to_numpy(dtype=float))
    else:
        soc = np.full(n, soc_default, dtype=float)
        soh = np.full(n, soh_default, dtype=float)
        lat = np.full(n, vehicle["home_lat"], dtype=float)
        lon = np.full(n, vehicle["home_lon"], dtype=float)
        odo = np.full(n, vehicle["odometer_start_km"], dtype=float)
        mean = float(ambient_cfg["mean"])
        batt_temp = np.full(n, mean + 6.0)
        motor_temp = np.full(n, mean + 8.0)
        inv_temp = np.full(n, mean + 5.0)

    mean = float(ambient_cfg["mean"])
    amp = float(ambient_cfg["amp"])
    is_car = vehicle.get("type", "car") == "car"

    if is_car:
        tires = {
            pos: np.full(n, vehicle["tire_pressure_base_bar"]) + rng.normal(0.0, 0.01, n)
            for pos in TIRE_POSITIONS
        }
    else:
        tires = {
            "fl": np.full(n, vehicle["tire_pressure_base_bar"]) + rng.normal(0.0, 0.01, n),
            "fr": np.full(n, vehicle["tire_pressure_base_bar"]) + rng.normal(0.0, 0.01, n),
            "rl": np.full(n, np.nan),
            "rr": np.full(n, np.nan),
        }

    ambient = ambient_curve(off_seconds.astype(float) / 60.0, mean, amp)

    cabin_temp = ambient + rng.normal(0, 0.5, n) if is_car else np.full(n, np.nan)
    hvac_kw = np.zeros(n)

    batt_avg = batt_temp
    batt_max = batt_temp

    a_x = np.zeros(n)
    a_y = np.zeros(n)
    a_z = np.full(n, 9.81) + rng.normal(0, 0.05, n)

    frame = build_frame(
        vehicle,
        day_start_iso,
        off_min,
        off_seconds,
        np.zeros(n),
        soc,
        soh,
        batt_temp,
        batt_avg,
        batt_max,
        np.full(n, "disconnected", dtype=object),
        np.zeros(n),
        motor_temp,
        inv_temp,
        np.full(n, "P", dtype=object),
        lat + rng.normal(0, 0.00002, n),
        lon + rng.normal(0, 0.00002, n),
        a_x, a_y, a_z,
        np.full(n, "locked", dtype=object),
        cabin_temp,
        hvac_kw,
        np.full(n, False, dtype=bool),
        odo,
        is_charging=False,
        charging_power_kw=np.zeros(n),
        ignition_on=False,
        ambient=ambient,
        tire_pressures=tires,
    )
    return frame
