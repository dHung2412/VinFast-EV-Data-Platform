from __future__ import annotations

import datetime
import pathlib
import string

import numpy as np
import pandas as pd

from src.data_generator.telemetry.entities import (
    CITIES,
    VEHICLE_MODELS,
    _random_phone,
    build_fleet_with_users,
    build_users,
)

# Bảng ký tự mã VIN hợp lệ theo chuẩn ISO 3779 (bỏ các ký tự dễ nhầm lẫn: I, O, Q)
VIN_CHARS = [c for c in string.ascii_uppercase + string.digits if c not in "IOQ"]

# Bảng ánh xạ tên mẫu xe sang mã hệ thống DMS
MODEL_CODE_MAP = {
    "VF 3": "VF3",
    "VF 5": "VF5",
    "VF e34": "VFe34",
    "VF 6": "VF6",
    "VF 7": "VF7",
    "VF 8": "VF8",
    "VF 9": "VF9",
    "VF Amio S": "VF_AMIO_S",
    "VF Evo Lite S": "VF_EVO_LITE_S",
    "VF Flazz S": "VF_FLAZZ_S",
}
INV_MODEL_CODES = list(MODEL_CODE_MAP.values())


def _random_vin(rng: np.random.Generator) -> str:
    """Sinh chuỗi mã số định danh phương tiện VIN ngẫu nhiên chuẩn 17 ký tự."""
    return "".join(str(rng.choice(VIN_CHARS)) for _ in range(17))


def build_dms_dealers(
    n_per_city: dict[str, int] | None = None,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """Sinh bảng dữ liệu danh sách đại lý phân phối VinFast (dealer.csv)."""
    if rng is None:
        rng = np.random.default_rng(42)

    n_per_city = n_per_city or {"HN": 3, "SG": 3, "DN": 2, "TH": 1, "TN": 1, "NA": 1, "HT": 1}
    rows = []

    for city, cnt in n_per_city.items():
        center = CITIES[city]
        for i in range(1, cnt + 1):
            code = f"DLR-{city}-{i:03d}"
            dtype = str(rng.choice(["flagship", "retail", "service"], p=[0.2, 0.6, 0.2]))
            rows.append(
                {
                    "dealer_code": code,
                    "dealer_name": f"VinFast {city} {dtype.title()} {i}",
                    "city": city,
                    "address": f"{int(rng.integers(1, 200))} {city} Street, {city}",
                    "lat": float(center["lat"] + rng.normal(0, 0.04)),
                    "lon": float(center["lon"] + rng.normal(0, 0.04)),
                    "dealer_type": dtype,
                }
            )

    return pd.DataFrame(rows)


def build_dms_sales_orders(
    n_orders: int = 20,
    rng: np.random.Generator | None = None,
    users: list[dict] | None = None,
    dealers_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Sinh bảng dữ liệu đơn hàng bán xe của hệ thống DMS (sales_order.csv)."""
    if rng is None:
        rng = np.random.default_rng(42)

    dealers = (
        dealers_df["dealer_code"].tolist()
        if dealers_df is not None
        else [f"DLR-HN-{i:03d}" for i in range(1, 4)]
    )

    # Ưu tiên lấy số điện thoại khách hàng từ CRM để đảm bảo tính nhất quán dữ liệu liên nguồn
    crm_phones: list[str] | None = None
    try:
        crm_path = pathlib.Path("data/raw/crm/customer.csv")
        if crm_path.exists():
            crm_df = pd.read_csv(crm_path, dtype=str)
            if "phone_number" in crm_df.columns:
                crm_phones = crm_df["phone_number"].dropna().astype(str).tolist()
    except Exception:
        crm_phones = None

    base_users = users or build_users(16, rng)
    rows = []
    colors = ["white", "black", "red", "blue", "grey", "silver"]
    pay_methods = ["cash", "bank_loan", "installment"]

    for i in range(n_orders):
        vin = _random_vin(rng)
        dealer = str(rng.choice(dealers))

        # Liên kết số điện thoại người mua: CRM -> Danh sách người dùng -> Tạo ngẫu nhiên
        if crm_phones:
            phone = str(rng.choice(crm_phones))
        elif base_users:
            phone = base_users[int(rng.integers(len(base_users)))]["phone"]
        else:
            phone = _random_phone(rng)

        # Ngày bán xe trong vòng 1 năm gần nhất
        days_ago = int(rng.integers(10, 400))
        sale_date = datetime.date.today() - datetime.timedelta(days=days_ago)
        sale = sale_date.isoformat()
        warranty = (sale_date + datetime.timedelta(days=7)).isoformat()

        model_code = str(rng.choice(INV_MODEL_CODES))

        # Đơn giá tham chiếu theo triệu VND
        price_map = {
            "VF3": 240,
            "VF5": 550,
            "VFe34": 710,
            "VF6": 850,
            "VF7": 999,
            "VF8": 1200,
            "VF9": 1600,
            "VF_AMIO_S": 30,
            "VF_EVO_LITE_S": 35,
            "VF_FLAZZ_S": 32,
        }
        base_price = price_map.get(model_code, 500)
        price = int(base_price * 1_000_000 * float(rng.uniform(0.95, 1.05)))

        rows.append(
            {
                "order_id": f"ORD-{i + 1:06d}",
                "vin": vin,
                "dealer_code": dealer,
                "customer_phone": phone,
                "sale_date": sale,
                "model_code": model_code,
                "color": str(rng.choice(colors)),
                "unit_price_vnd": price,
                "payment_method": str(rng.choice(pay_methods, p=[0.3, 0.4, 0.3])),
                "warranty_start": warranty,
            }
        )

    return pd.DataFrame(rows)


def build_dms_inventory(
    n: int = 30,
    rng: np.random.Generator | None = None,
    dealers_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Sinh bảng dữ liệu danh mục tồn kho xe tại các đại lý DMS (inventory.csv)."""
    if rng is None:
        rng = np.random.default_rng(42)

    dealers = (
        dealers_df["dealer_code"].tolist()
        if dealers_df is not None
        else [f"DLR-HN-{i:03d}" for i in range(1, 4)]
    )

    rows = []
    statuses = ["in_stock", "sold", "reserved"]

    for _ in range(n):
        vin = _random_vin(rng)
        dealer = str(rng.choice(dealers))
        model_code = str(rng.choice(INV_MODEL_CODES))

        days_ago = int(rng.integers(0, 90))
        stock_in = (datetime.date.today() - datetime.timedelta(days=days_ago)).isoformat()

        rows.append(
            {
                "vin": vin,
                "model_code": model_code,
                "color": str(rng.choice(["white", "black", "red", "blue"])),
                "dealer_code": dealer,
                "stock_in_date": stock_in,
                "status": str(rng.choice(statuses, p=[0.6, 0.3, 0.1])),
            }
        )

    return pd.DataFrame(rows)


def write_dms_raw(
    output_base: pathlib.Path = pathlib.Path("data/raw/dms"),
    seed: int = 42,
) -> None:
    """Khởi tạo và ghi các tệp dữ liệu giả lập DMS (dealer.csv, sales_order.csv, inventory.csv) dạng CSV."""
    rng = np.random.default_rng(seed)
    users = build_users(16, rng)
    dealers = build_dms_dealers(rng=rng)
    orders = build_dms_sales_orders(n_orders=20, rng=rng, users=users, dealers_df=dealers)
    inventory = build_dms_inventory(n=30, rng=rng, dealers_df=dealers)

    output_base.mkdir(parents=True, exist_ok=True)
    dealers.to_csv(output_base / "dealer.csv", index=False, encoding="utf-8")
    orders.to_csv(output_base / "sales_order.csv", index=False, encoding="utf-8")
    inventory.to_csv(output_base / "inventory.csv", index=False, encoding="utf-8")

    print(f"DMS mock: {len(dealers)} dealers -> {output_base / 'dealer.csv'}")
    print(f"DMS mock: {len(orders)} orders -> {output_base / 'sales_order.csv'}")
    print(f"DMS mock: {len(inventory)} inventory -> {output_base / 'inventory.csv'}")


if __name__ == "__main__":
    write_dms_raw()
