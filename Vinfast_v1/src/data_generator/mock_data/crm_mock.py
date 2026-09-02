from __future__ import annotations

import datetime
import pathlib

import numpy as np
import pandas as pd

from src.data_generator.telemetry.entities import (
    CITIES,
    _random_phone,
    _random_viet_name,
    build_users,
)


def _random_email(name: str, rng: np.random.Generator) -> str | None:
    """Sinh ngẫu nhiên địa chỉ email từ tên người dùng (10% xác suất để trống email)."""
    if rng.random() < 0.10:
        return None

    local = name.lower().replace(" ", ".") + str(int(rng.integers(10, 99)))
    domain = str(rng.choice(["gmail.com", "yahoo.com", "outlook.com", "vinfast.vn"]))

    return f"{local}@{domain}"


def build_crm_customers(
    n: int = 40,
    rng: np.random.Generator | None = None,
    users: list[dict] | None = None,
) -> pd.DataFrame:
    """Sinh bảng dữ liệu danh sách khách hàng CRM (customer.csv)."""
    if rng is None:
        rng = np.random.default_rng(42)

    rows = []
    city_codes = list(CITIES.keys())
    statuses = ["active", "inactive", "lead", "churned"]
    status_p = [0.6, 0.1, 0.2, 0.1]

    base_users = users or build_users(n, rng)

    for i in range(n):
        # Tái sử dụng số điện thoại của người dùng ứng dụng để liên kết dữ liệu (85% xác suất)
        if i < len(base_users) and rng.random() < 0.85:
            u = base_users[int(rng.integers(len(base_users)))]
            phone = u["phone"]
            name = u["name"]
        else:
            # Tạo người dùng mới ngẫu nhiên
            name = _random_viet_name(rng)
            phone = _random_phone(rng)

        email = _random_email(name, rng)
        city = str(rng.choice(city_codes))

        # Ngày đăng ký ngẫu nhiên trong vòng 2 năm gần nhất
        days_ago = int(rng.integers(0, 730))
        reg = (datetime.date.today() - datetime.timedelta(days=days_ago)).isoformat()

        # Giả lập định dạng số điện thoại biến thể (+84 hoặc khoảng trắng)
        phone_out = phone
        if rng.random() < 0.2:
            phone_out = "+84" + phone[1:]
        elif rng.random() < 0.2:
            phone_out = phone[:3] + " " + phone[3:6] + " " + phone[6:]

        rows.append(
            {
                "customer_code": f"CUS-CRM-{i + 1:05d}",
                "full_name": name,
                "phone_number": phone_out,
                "email": email if email else "",
                "customer_status": str(rng.choice(statuses, p=status_p)),
                "registered_date": reg,
                "city": city,
            }
        )

    return pd.DataFrame(rows)


def build_crm_interactions(
    customers_df: pd.DataFrame,
    n: int = 80,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """Sinh bảng dữ liệu lịch sử tương tác khách hàng CRM (interaction.csv)."""
    if rng is None:
        rng = np.random.default_rng(42)

    types = ["call", "email", "visit", "test_drive", "complaint", "purchase"]
    type_p = [0.30, 0.15, 0.20, 0.20, 0.10, 0.05]
    rows = []
    phones = customers_df["phone_number"].tolist()

    for i in range(n):
        phone = str(rng.choice(phones))
        itype = str(rng.choice(types, p=type_p))
        days_ago = int(rng.integers(0, 60))
        date_str = (datetime.date.today() - datetime.timedelta(days=days_ago)).isoformat()

        rows.append(
            {
                "interaction_id": f"INT-{i + 1:06d}",
                "phone_number": phone,
                "interaction_type": itype,
                "interaction_date": date_str,
                "outcome": str(
                    rng.choice(["success", "pending", "failed", "no_answer"], p=[0.5, 0.2, 0.15, 0.15])
                ),
                "agent_name": f"Agent-{int(rng.integers(1, 10)):02d}",
                "notes": f"Ghi chú cho lượt {itype} #{i + 1}",
            }
        )

    return pd.DataFrame(rows)


def write_crm_raw(
    output_base: pathlib.Path = pathlib.Path("data/raw/crm"),
    seed: int = 42,
    n_customers: int = 40,
) -> None:
    """Khởi tạo và ghi tập dữ liệu CRM giả lập (customer.csv, interaction.csv) dạng CSV."""
    rng = np.random.default_rng(seed)
    users = build_users(16, rng)

    customers = build_crm_customers(n=n_customers, rng=rng, users=users)
    interactions = build_crm_interactions(customers, n=max(20, n_customers * 2), rng=rng)

    output_base.mkdir(parents=True, exist_ok=True)
    customers.to_csv(output_base / "customer.csv", index=False, encoding="utf-8")
    interactions.to_csv(output_base / "interaction.csv", index=False, encoding="utf-8")

    print(f"CRM mock: {len(customers)} customers -> {output_base / 'customer.csv'}")
    print(f"CRM mock: {len(interactions)} interactions -> {output_base / 'interaction.csv'}")


if __name__ == "__main__":
    write_crm_raw()
