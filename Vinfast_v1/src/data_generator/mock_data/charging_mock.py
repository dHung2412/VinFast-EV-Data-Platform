# Nguồn thu thập từ trạm sạc (external)
from __future__ import annotations

import datetime
import pathlib
import string

import numpy as np
import pandas as pd

from src.data_generator.telemetry.entities import build_stations

# Bảng ký tự mã VIN hợp lệ theo chuẩn ISO 3779 (bỏ các ký tự dễ nhầm lẫn: I, O, Q)
VIN_CHARS = [c for c in string.ascii_uppercase + string.digits if c not in "IOQ"]


def _random_vin(rng: np.random.Generator) -> str:
    """Sinh chuỗi mã số định danh phương tiện VIN ngẫu nhiên chuẩn 17 ký tự."""
    return "".join(str(rng.choice(VIN_CHARS)) for _ in range(17))


def build_charging_external(
    n: int = 30,
    rng: np.random.Generator | None = None,
    stations: list[dict] | None = None,
    vins: list[str] | None = None,
) -> pd.DataFrame:
    """Sinh bảng dữ liệu các phiên sạc pin bên ngoài / từ đối tác (charging_session.csv)."""
    if rng is None:
        rng = np.random.default_rng(42)

    if stations is None:
        stations = build_stations(rng)

    station_ids = [s["station_id"] for s in stations]
    st_map = {s["station_id"]: s["charger_type"] for s in stations}
    rows = []

    for i in range(n):
        station = str(rng.choice(station_ids))
        charger_type = st_map[station]

        # Tỷ lệ 85% có mã VIN khớp với DMS (xe đã bán), 30% vãng lai hoặc để trống mã VIN
        if rng.random() < 0.85 and vins:
            vin = str(rng.choice(vins)) if vins else _random_vin(rng)
        elif rng.random() < 0.5:
            vin = _random_vin(rng)
        else:
            vin = ""

        connector = f"CONN-{int(rng.integers(1, 5)):02d}"

        # Thời điểm bắt đầu sạc trong vòng 7 ngày gần nhất, thời lượng sạc 20-180 phút
        days_ago = int(rng.integers(0, 7))
        start_hour = int(rng.integers(6, 22))
        start_time = datetime.datetime.combine(
            datetime.date.today() - datetime.timedelta(days=days_ago),
            datetime.time(start_hour, int(rng.integers(0, 60))),
        )
        duration_min = int(rng.integers(20, 180))
        end_time = start_time + datetime.timedelta(minutes=duration_min)

        kwh = float(rng.uniform(5, 80))
        cost = int(kwh * float(rng.uniform(3000, 4500)))

        rows.append(
            {
                "session_id": f"SESS-EXT-{i + 1:06d}",
                "vin": vin,
                "station_id": station,
                "connector_id": connector,
                "charger_type": charger_type,
                "started_at": start_time.isoformat(),
                "ended_at": end_time.isoformat(),
                "kwh_delivered": round(kwh, 2),
                "cost_vnd": cost,
                "payment_method": str(
                    rng.choice(["app", "rfid_card", "credit_card", "cash"], p=[0.5, 0.2, 0.2, 0.1])
                ),
            }
        )

    df = pd.DataFrame(rows)
    # Chuyển đổi mã VIN rỗng thành None để phù hợp với định dạng Nullable của Schema
    df["vin"] = df["vin"].replace("", None)
    return df


def write_charging_raw(
    output_base: pathlib.Path = pathlib.Path("data/raw/charging"),
    seed: int = 42,
) -> None:
    """Khởi tạo và ghi tệp dữ liệu giả lập phiên sạc (charging_session.csv) dạng CSV."""
    rng = np.random.default_rng(seed)
    stations = build_stations(rng)

    # Đọc mã VIN từ dữ liệu bán hàng DMS để liên kết nhất quán dữ liệu liên nguồn (charging_vehicle_exists)
    vins: list[str] = []
    dms_path = pathlib.Path("data/raw/dms/sales_order.csv")
    if dms_path.exists():
        try:
            dms_df = pd.read_csv(dms_path, dtype=str)
            vins = dms_df["vin"].dropna().astype(str).tolist()
        except Exception:
            vins = []

    if not vins:
        vins = [_random_vin(rng) for _ in range(10)]

    df = build_charging_external(n=30, rng=rng, stations=stations, vins=vins)

    output_base.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_base / "charging_session.csv", index=False, encoding="utf-8")

    print(
        f"Charging mock: {len(df)} sessions ({len(vins)} DMS-linked VINs) -> {output_base / 'charging_session.csv'}"
    )


if __name__ == "__main__":
    write_charging_raw()
