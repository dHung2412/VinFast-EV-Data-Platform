from __future__ import annotations

import argparse
import pathlib
from datetime import date, datetime, timedelta

import pandas as pd

from src.data_generator.mock_data.charging_mock import write_charging_raw
from src.data_generator.mock_data.crm_mock import write_crm_raw
from src.data_generator.mock_data.dms_mock import write_dms_raw
from src.data_generator.telemetry.charging_sessions import (
    extract_charging_sessions_from_telemetry,
)
from src.data_generator.telemetry.entities import (
    build_fleet_with_users,
    build_stations,
    build_users,
)
from src.data_generator.telemetry.vehicle_telemetry import generate_telemetry_day
from src.data_generator.utils import make_rng


def _parse_date(s: str) -> date:
    """Định dạng chuỗi ngày YYYY-MM-DD sang đối tượng datetime.date."""
    return datetime.strptime(s, "%Y-%m-%d").date()


def _write_hive_parquet(df: pd.DataFrame, base: pathlib.Path, dataset: str, day: date) -> None:
    """Ghi dữ liệu DataFrame ra định dạng Parquet theo phân vùng Hive (year=/month=/day=)."""
    out_dir = base / dataset / f"year={day.year:04d}" / f"month={day.month:02d}" / f"day={day.day:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "part-0000.parquet"

    # Lọc bỏ các cột phụ tạm thời dùng cho phân đoạn mô phỏng
    drop_cols = [c for c in ["day_start", "_off_min", "_off_seconds"] if c in df.columns]
    to_write = df.drop(columns=drop_cols) if drop_cols else df

    to_write.to_parquet(
        out_path,
        index=False,
        engine="pyarrow",
        coerce_timestamps="us",
        allow_truncated_timestamps=True,
    )


def cmd_generate(args: argparse.Namespace) -> None:
    """Lệnh sinh dữ liệu mô phỏng chính (Entities, Telemetry & Charging Sessions)."""
    start = _parse_date(args.start_date)
    end = _parse_date(args.end_date)
    if end < start:
        raise SystemExit("Lỗi: --end-date phải lớn hơn hoặc bằng --start-date")

    n_vehicles = args.vehicles
    n_users = args.users
    if n_users is None:
        # Tự động tính số người dùng tương ứng (trung bình ~1.25 xe/người dùng)
        n_users = max(5, int(n_vehicles / 1.25 + 0.5))
        n_users = min(n_users, 80)

    seed = args.seed
    out_base = pathlib.Path(args.output)
    datasets = set(s.strip() for s in args.datasets.split(",") if s.strip())
    valid = {"telemetry", "charging_sessions", "users", "vehicles", "stations", "all"}

    if not datasets.issubset(valid):
        raise SystemExit(f"Lỗi: datasets phải thuộc tập {valid}, nhận được {datasets}")

    if "all" in datasets:
        datasets = {"telemetry", "charging_sessions", "users", "vehicles", "stations"}

    rng = make_rng(seed, "entities")
    users = build_users(n_users, rng)
    fleet = build_fleet_with_users(users, rng)
    stations = build_stations(rng)

    # 1. Ghi tập dữ liệu thực thể tĩnh (Entities)
    ent_base = out_base / "entities"
    if datasets & {"users", "vehicles", "stations"}:
        ent_base.mkdir(parents=True, exist_ok=True)

    if "users" in datasets:
        pd.DataFrame(users).to_parquet(
            ent_base / "users.parquet",
            index=False,
            engine="pyarrow",
            coerce_timestamps="us",
            allow_truncated_timestamps=True,
        )
        print(f"Đã ghi {len(users)} người dùng -> {ent_base / 'users.parquet'}")

    if "vehicles" in datasets:
        pd.DataFrame(fleet).to_parquet(
            ent_base / "vehicles.parquet",
            index=False,
            engine="pyarrow",
            coerce_timestamps="us",
            allow_truncated_timestamps=True,
        )
        print(f"Đã ghi {len(fleet)} phương tiện -> {ent_base / 'vehicles.parquet'}")

    if "stations" in datasets:
        pd.DataFrame(stations).to_parquet(
            ent_base / "stations.parquet",
            index=False,
            engine="pyarrow",
            coerce_timestamps="us",
            allow_truncated_timestamps=True,
        )
        print(f"Đã ghi {len(stations)} trạm sạc -> {ent_base / 'stations.parquet'}")

    # 2. Sinh chuỗi dữ liệu Telemetry và Phiên sạc theo từng ngày
    day = start
    total_tele_rows = 0
    total_sess_rows = 0

    while day <= end:
        if datasets & {"telemetry", "charging_sessions"}:
            tele = generate_telemetry_day(fleet, day, seed)

            if "telemetry" in datasets:
                _write_hive_parquet(tele, out_base, "telemetry", day)
                total_tele_rows += len(tele)
                print(f"[{day}] Telemetry: {len(tele)} dòng")

            if "charging_sessions" in datasets:
                sess = extract_charging_sessions_from_telemetry(tele, stations, seed)
                if not sess.empty:
                    _write_hive_parquet(sess, out_base, "charging_sessions", day)
                else:
                    # Ghi phân vùng rỗng đúng lược đồ nếu không có phiên sạc trong ngày
                    empty = pd.DataFrame(
                        columns=[
                            "session_id", "vehicle_id", "station_id", "charger_type", "power_kw",
                            "started_at", "ended_at", "duration_min", "kwh_delivered",
                            "start_soc_pct", "end_soc_pct", "cost_vnd", "payment_method"
                        ]
                    )
                    _write_hive_parquet(empty, out_base, "charging_sessions", day)

                total_sess_rows += len(sess)
                print(f"[{day}] Phiên sạc (charging_sessions): {len(sess)} dòng")

        day += timedelta(days=1)

    print(f"Hoàn tất. Tổng số dòng Telemetry: {total_tele_rows}, Phiên sạc: {total_sess_rows}")


def cmd_mock_raw(args: argparse.Namespace) -> None:
    """Lệnh sinh các tập dữ liệu thô giả lập cho hệ thống CRM, DMS và Charging."""
    seed = args.seed
    if args.source in ("all", "crm"):
        write_crm_raw(seed=seed, n_customers=args.n_customers)
    if args.source in ("all", "dms"):
        write_dms_raw(seed=seed)
    if args.source in ("all", "charging"):
        write_charging_raw(seed=seed)


def build_parser() -> argparse.ArgumentParser:
    """Khởi tạo trình xử lý đối số dòng lệnh (CLI Argument Parser)."""
    p = argparse.ArgumentParser(prog="python -m src.data_generator.cli")
    sub = p.add_subparsers(dest="command", required=True)

    # Sub-command: generate
    g = sub.add_parser("generate", help="Sinh các tập dữ liệu tổng hợp (Telemetry, Entities, Sessions)")
    g.add_argument("--start-date", required=True, help="Ngày bắt đầu (YYYY-MM-DD)")
    g.add_argument("--end-date", required=True, help="Ngày kết thúc (YYYY-MM-DD)")
    g.add_argument("--vehicles", type=int, default=20, help="Số lượng phương tiện")
    g.add_argument("--users", type=int, default=None, help="Số lượng người dùng (tự động nếu để trống)")
    g.add_argument("--seed", type=int, default=42, help="Hạt giống ngẫu nhiên (Random seed)")
    g.add_argument("--output", type=str, default="data/raw", help="Thư mục đầu ra")
    g.add_argument(
        "--datasets",
        type=str,
        default="all",
        help="Danh sách tập dữ liệu phân cách bởi dấu phẩy: telemetry,charging_sessions,users,vehicles,stations,all",
    )
    g.set_defaults(func=cmd_generate)

    # Sub-command: mock-raw
    m = sub.add_parser("mock-raw", help="Sinh dữ liệu giả lập CSV cho CRM, DMS và Charging")
    m.add_argument("--source", type=str, default="all", choices=["all", "crm", "dms", "charging"])
    m.add_argument("--seed", type=int, default=42, help="Hạt giống ngẫu nhiên")
    m.add_argument("--n-customers", type=int, default=40, help="Số lượng khách hàng CRM")
    m.set_defaults(func=cmd_mock_raw)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
