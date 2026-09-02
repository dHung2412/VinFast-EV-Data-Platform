from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.data_generator.telemetry.vehicle_telemetry import generate_telemetry_day
from src.data_generator.utils import make_rng, stable_id

# Múi giờ địa phương và múi giờ chuẩn quốc tế
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC = timezone.utc

# Đơn giá sạc điện tham chiếu (VND/kWh)
RATES_VND_PER_KWH = {
    "AC_TYPE2": 2948.0,  # Đơn giá sạc chậm AC
    "CCS2_DC": 3948.0,   # Đơn giá sạc nhanh DC
}

# Danh sách các cột thuộc lược đồ bảng dữ liệu Phiên sạc (Charging Sessions)
COLUMNS = [
    "session_id",      # Mã định danh phiên sạc
    "vehicle_id",      # Mã phương tiện
    "station_id",      # Mã trạm sạc
    "charger_type",    # Chuẩn cổng sạc (AC_TYPE2 hoặc CCS2_DC)
    "power_kw",        # Công suất sạc (kW)
    "started_at",      # Thời điểm bắt đầu sạc (UTC)
    "ended_at",        # Thời điểm kết thúc sạc (UTC)
    "duration_min",    # Thời lượng sạc (phút)
    "kwh_delivered",   # Điện năng tiêu thụ thực tế (kWh)
    "start_soc_pct",   # Mức pin đầu phiên (%)
    "end_soc_pct",     # Mức pin cuối phiên (%)
    "cost_vnd",        # Chi phí thanh toán (VND)
    "payment_method",  # Phương thức thanh toán (VinFast App / RFID Card)
]


def _nearest_station(lat: float, lon: float, stations: list[dict]) -> dict | None:
    """Tìm trạm sạc có tọa độ địa lý gần nhất với vị trí hiện tại của xe."""
    if not stations:
        return None

    best = None
    best_d2 = float("inf")

    for st in stations:
        dlat = st["lat"] - lat
        dlon = st["lon"] - lon
        d2 = dlat * dlat + dlon * dlon
        if d2 < best_d2:
            best_d2 = d2
            best = st

    return best


def extract_charging_sessions_from_telemetry(
    df_telemetry: pd.DataFrame,
    stations: list[dict],
    seed: int | None = None,
) -> pd.DataFrame:
    """Trích xuất danh sách các phiên sạc pin từ dữ liệu Telemetry của xe (Single Source of Truth)."""
    if df_telemetry.empty or "is_charging" not in df_telemetry.columns:
        return pd.DataFrame(columns=COLUMNS)

    # Lọc các dòng dữ liệu trong trạng thái đang sạc (is_charging == True)
    charging = df_telemetry[df_telemetry["is_charging"] == True].copy()  # noqa: E712
    if charging.empty:
        return pd.DataFrame(columns=COLUMNS)

    # Sắp xếp thứ tự dữ liệu theo phương tiện và mốc thời gian
    if "_off_seconds" in charging.columns:
        charging = charging.sort_values(["vehicle_id", "_off_seconds"])
    else:
        charging = charging.sort_values(["vehicle_id", "event_timestamp"])

    records: list[dict] = []

    # Gom nhóm dữ liệu theo từng xe để xác định các phiên sạc liên tục
    for vehicle_id, group in charging.groupby("vehicle_id", sort=False):
        g = group.sort_values("event_timestamp").reset_index(drop=True)

        # Phát hiện sự gián đoạn: khoảng cách thời gian giữa 2 mẫu > 120 giây tương ứng với phiên sạc mới
        if "_off_seconds" in g.columns:
            secs = g["_off_seconds"].to_numpy(dtype="int64")
            gaps = np.diff(secs, prepend=secs[0])
            new_session = np.concatenate([[True], gaps[1:] > 120])
        else:
            ts = pd.to_datetime(g["event_timestamp"])
            gaps_s = ts.diff().dt.total_seconds().fillna(0).to_numpy()
            new_session = np.concatenate([[True], gaps_s[1:] > 120])

        session_id_counter = 0
        start_idx = 0

        for i in range(1, len(g) + 1):
            is_break = (i == len(g)) or bool(new_session[i])
            if is_break:
                end_idx = i - 1
                seg = g.iloc[start_idx : end_idx + 1]

                # Bỏ qua các chuỗi quá ngắn (< 2 mẫu dữ liệu)
                if len(seg) >= 2:
                    rec = _segment_to_session(seg, stations, seed, session_id_counter)
                    if rec is not None:
                        records.append(rec)
                        session_id_counter += 1

                start_idx = i

    df = pd.DataFrame(records, columns=COLUMNS)
    if df.empty:
        return df

    # Đảm bảo chuẩn hóa múi giờ UTC cho các mốc thời gian
    df["started_at"] = pd.to_datetime(df["started_at"], utc=True)
    df["ended_at"] = pd.to_datetime(df["ended_at"], utc=True)

    return df.sort_values(["started_at", "session_id"]).reset_index(drop=True)


def _segment_to_session(
    seg: pd.DataFrame, stations: list[dict], seed: int | None, counter: int
) -> dict | None:
    """Chuyển đổi một phân đoạn dữ liệu sạc telemetry liên tục thành bản ghi phiên sạc hoàn chỉnh."""
    vehicle_id = str(seg["vehicle_id"].iloc[0])
    started_at = pd.to_datetime(seg["event_timestamp"].iloc[0], utc=True)
    ended_at = pd.to_datetime(seg["event_timestamp"].iloc[-1], utc=True)

    # Tính tổng thời lượng sạc (phút)
    if "_off_seconds" in seg.columns:
        dur_s = int(seg["_off_seconds"].iloc[-1] - seg["_off_seconds"].iloc[0])
        dt_last = (
            int(np.clip(int(seg["_off_seconds"].iloc[-1] - seg["_off_seconds"].iloc[-2]), 10, 60))
            if len(seg) > 1
            else 30
        )
        dur_min = (dur_s + dt_last) / 60.0
    else:
        dur_min = (ended_at - started_at).total_seconds() / 60.0
        if dur_min < 0.5:
            dur_min = len(seg) * 0.5

    start_soc = float(seg["battery_soc_pct"].iloc[0])
    end_soc = float(seg["battery_soc_pct"].iloc[-1])

    # Xác định công suất sạc trung bình và công suất cực đại
    if "charging_power_kw" in seg.columns:
        pw = seg["charging_power_kw"].to_numpy(dtype=float)
        pw = pw[~np.isnan(pw)]
        if len(pw) == 0:
            pw_mean = 11.0
            pw_max = 11.0
        else:
            pw_mean = float(np.mean(pw[pw > 0])) if (pw > 0).any() else float(np.mean(pw))
            pw_max = float(np.max(pw))
    else:
        pw_mean = 11.0
        pw_max = 11.0

    # Phân loại chuẩn sạc (DC sạc nhanh vs AC sạc chậm)
    if "charging_status" in seg.columns:
        statuses = seg["charging_status"].astype(str).tolist()
        if any(s == "charging_dc_fast" for s in statuses):
            charger_type = "CCS2_DC"
        elif any(s == "charging_ac" for s in statuses):
            charger_type = "AC_TYPE2"
        elif pw_max >= 50:
            charger_type = "CCS2_DC"
        else:
            charger_type = "AC_TYPE2"
    else:
        charger_type = "CCS2_DC" if pw_max >= 50 else "AC_TYPE2"

    # Tính tổng điện năng sạc tích lũy (kWh)
    if "_off_seconds" in seg.columns:
        secs = seg["_off_seconds"].to_numpy(dtype="int64")
        dts = np.diff(secs, prepend=secs[0])
        if len(dts) > 1:
            median_dt = float(np.median(dts[1:])) if len(dts) > 2 else 30.0
            dts[0] = int(median_dt)
        else:
            dts[0] = 30

        pws = (
            seg["charging_power_kw"].to_numpy(dtype=float)
            if "charging_power_kw" in seg.columns
            else np.full(len(seg), pw_mean)
        )
        pws = np.where(np.isnan(pws), 0, pws)
        kwh = float(np.sum(pws * dts / 3600.0))
    else:
        ts = pd.to_datetime(seg["event_timestamp"], utc=True)
        dts = ts.diff().dt.total_seconds().fillna(0).to_numpy()
        if len(dts) > 1:
            median_dt = float(np.median(dts[1:][dts[1:] > 0])) if (dts[1:] > 0).any() else 30.0
            dts[0] = median_dt

        pws = (
            seg["charging_power_kw"].to_numpy(dtype=float)
            if "charging_power_kw" in seg.columns
            else np.full(len(seg), pw_mean)
        )
        pws = np.where(np.isnan(pws), 0, pws)
        kwh = float(np.sum(pws * dts / 3600.0))
        if kwh < 0.01:
            kwh = float(pw_mean * dur_min / 60.0)

    # Tìm trạm sạc gần nhất dựa theo trung bình tọa độ GPS
    lat = float(seg["latitude"].mean()) if "latitude" in seg.columns else 21.0
    lon = float(seg["longitude"].mean()) if "longitude" in seg.columns else 105.8
    station = _nearest_station(lat, lon, stations) if stations else None
    station_id = station["station_id"] if station else f"CS-UNK-{counter:03d}"

    # Tính tổng chi phí sạc VND (tải cao điểm 17h-21h với sạc DC áp nhân hệ số 1.2)
    started_local = started_at.tz_convert(LOCAL_TZ)
    local_hour = started_local.hour + started_local.minute / 60.0
    peak_mult = 1.2 if (17.0 <= local_hour < 21.0 and charger_type == "CCS2_DC") else 1.0
    rate = RATES_VND_PER_KWH.get(charger_type, 2948.0)
    cost = round(kwh * rate * peak_mult, -3)

    # Phương thức thanh toán ngẫu nhiên định đề (VinFast App 75% / Card RFID 25%)
    if seed is not None:
        rng = make_rng(seed, "payment", vehicle_id, str(started_at))
        pm = str(rng.choice(["VinFast App", "RFID Card"], p=[0.75, 0.25]))
    else:
        pm = "VinFast App"

    sid = stable_id("sess", vehicle_id, started_at.isoformat())

    return {
        "session_id": sid,
        "vehicle_id": vehicle_id,
        "station_id": station_id,
        "charger_type": charger_type,
        "power_kw": round(pw_max, 1) if not np.isnan(pw_max) else round(pw_mean, 1),
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_min": round(float(dur_min), 1),
        "kwh_delivered": round(float(kwh), 2),
        "start_soc_pct": round(float(start_soc), 1),
        "end_soc_pct": round(float(end_soc), 1),
        "cost_vnd": cost,
        "payment_method": pm,
    }


def generate_charging_sessions_for_day(
    fleet: list[dict], stations: list[dict], day: date, seed: int
) -> pd.DataFrame:
    """Tạo dữ liệu các phiên sạc trong một ngày bằng cách mô phỏng Telemetry rồi trích xuất."""
    tele = generate_telemetry_day(fleet, day, seed)
    return extract_charging_sessions_from_telemetry(tele, stations, seed)


def generate_charging_sessions(
    fleet: list[dict], stations: list[dict], start_date: date, end_date: date, seed: int
) -> pd.DataFrame:
    """Tạo dữ liệu các phiên sạc pin trong một khoảng thời gian (từ start_date đến end_date)."""
    frames = []
    day = start_date

    while day <= end_date:
        frames.append(generate_charging_sessions_for_day(fleet, stations, day, seed))
        day += timedelta(days=1)

    if not frames:
        return pd.DataFrame(columns=COLUMNS)

    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return df

    return df.sort_values(["started_at", "session_id"]).reset_index(drop=True)
