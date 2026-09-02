"""Thiết lập tự động Metabase cho hệ thống VinFast Analytics:
- Khởi tạo tài khoản quản trị Admin
- Kết nối tới cơ sở dữ liệu ClickHouse
- Tạo các bảng điều khiển (Dashboards) và thẻ biểu đồ (Cards) theo cấu hình

Cú pháp thực thi:
    python metabase/setup_dashboards.py [--base-url http://localhost:3000]
"""

from __future__ import annotations

import argparse
import time
from typing import Any, TypedDict

import requests

BASE_URL = "http://localhost:3000"
EMAIL = "admin@vinfast.vn"
PASSWORD = "Vinfast123!"
SITE_NAME = "VinFast Analytics"

# Định nghĩa kiểu dữ liệu cho thông số Dashboard và Card
KpiSpec = tuple[str, str]  # (Tên KPI, SQL truy vấn scalar)
CardSpec = tuple[str, str, str, dict[str, Any]]  # (Tên card, Loại hiển thị, SQL, Cấu hình giao diện)


class DashboardSpec(TypedDict):
    name: str
    description: str
    kpis: list[KpiSpec]
    cards: list[CardSpec]


def wait_metabase(base_url: str, timeout: int = 240) -> None:
    """Chờ dịch vụ Metabase khởi động và sẵn sàng nhận kết nối API."""
    for _ in range(timeout // 5):
        try:
            if requests.get(f"{base_url}/api/health", timeout=5).ok:
                return
        except Exception:
            pass
        time.sleep(5)

    raise RuntimeError("Dịch vụ Metabase không phản hồi qua /api/health")


def setup_admin(base_url: str) -> None:
    """Khởi tạo tài khoản quản trị Admin ban đầu nếu hệ thống chưa thiết lập."""
    props = requests.get(f"{base_url}/api/session/properties", timeout=10).json()

    if props.get("has-user-setup"):
        print("Metabase đã có tài khoản quản trị, bỏ qua bước khởi tạo.")
        return

    token = props.get("setup-token")
    if not token:
        raise RuntimeError("Không tìm thấy setup-token cho việc khởi tạo Metabase.")

    response = requests.post(
        f"{base_url}/api/setup",
        json={
            "token": token,
            "user": {
                "first_name": "Admin",
                "last_name": "VinFast",
                "email": EMAIL,
                "password": PASSWORD,
                "site_manager": True,
            },
            "prefs": {"site_name": SITE_NAME, "site_locale": "vi", "allow_tracking": False},
            "database": None,
        },
        timeout=30,
    )
    response.raise_for_status()
    print(f"Đã khởi tạo thành công tài khoản quản trị: {EMAIL}")


def login(base_url: str) -> dict[str, str]:
    """Đăng nhập và trả về Header phiên làm việc Session Token."""
    response = requests.post(
        f"{base_url}/api/session",
        json={"username": EMAIL, "password": PASSWORD},
        timeout=10,
    )
    response.raise_for_status()
    return {"X-Metabase-Session": response.json()["id"]}


def add_clickhouse(base_url: str, headers: dict[str, str]) -> int:
    """Thêm kết nối cơ sở dữ liệu ClickHouse vào Metabase."""
    dbs = requests.get(f"{base_url}/api/database", headers=headers, timeout=10).json()

    for db in dbs.get("data", []):
        if db.get("engine") == "clickhouse":
            print(f"Đã có kết nối ClickHouse sẵn có với Database ID = {db['id']}")
            return db["id"]

    response = requests.post(
        f"{base_url}/api/database",
        headers=headers,
        json={
            "engine": "clickhouse",
            "name": "VinFast ClickHouse",
            "details": {
                "host": "clickhouse",
                "port": 8123,
                "dbname": "vinfast",
                "user": "vinfast",
                "password": "vinfast123",
                "ssl": False,
                "tunnel_enabled": False,
            },
            "is_full_sync": True,
        },
        timeout=60,
    )
    response.raise_for_status()
    db_id = response.json()["id"]
    print(f"Đã thiết lập kết nối ClickHouse thành công, Database ID = {db_id}")
    return db_id


# =============================================================================
# DANH SÁCH BẢNG ĐIỀU KHIỂN (DASHBOARDS DEFINITION)
# =============================================================================
DASHBOARDS: list[DashboardSpec] = [
    # ------------------------------------------------------------- Dashboard Tổng quan --
    {
        "name": "VinFast EV — Tổng quan hoạt động",
        "description": "Bảng điều khiển tổng hợp các chỉ số: CRM khách hàng, Kênh bán hàng, Trạm sạc và Đội xe vận hành",
        "kpis": [
            ("Tổng khách hàng", "SELECT count() AS customers FROM mart_customer_360"),
            ("Tổng xe trong đội", "SELECT count() AS vehicles FROM mart_vehicle_360"),
            ("Tổng phiên sạc ngoài", "SELECT sum(session_count) AS sessions FROM mart_charging_revenue"),
        ],
        "cards": [
            (
                "Khách hàng theo giai đoạn vòng đời",
                "pie",
                "SELECT lifecycle_stage, count() AS customers FROM mart_customer_360 GROUP BY 1 ORDER BY 2 DESC",
                {"pie.show_legend": True},
            ),
            (
                "Doanh thu bán hàng theo đại lý (tỷ VND)",
                "bar",
                "SELECT dealer_name, round(total_revenue_vnd / 1e9, 2) AS revenue_bn_vnd FROM mart_sales_pipeline ORDER BY total_revenue_vnd DESC LIMIT 10",
                {},
            ),
            (
                "Doanh thu trạm sạc ngoài (triệu VND)",
                "bar",
                "SELECT charger_type, round(sum(total_revenue_vnd) / 1e6, 1) AS revenue_m_vnd FROM mart_charging_revenue GROUP BY 1 ORDER BY 2 DESC",
                {},
            ),
            (
                "SOC pin trung bình đội xe theo ngày (%)",
                "line",
                "SELECT activity_date, round(avg_fleet_soc_pct, 1) AS avg_soc_pct FROM mart_daily_fleet ORDER BY 1",
                {},
            ),
            (
                "Top 5 xe theo quãng đường tích lũy",
                "table",
                "SELECT vehicle_id, model, city_code, round(total_distance_km) AS distance_km, round(current_soh_pct, 1) AS soh_pct FROM mart_vehicle_360 ORDER BY total_distance_km DESC LIMIT 5",
                {"table.column_widths": [110, 130, 80, 110, 90]},
            ),
            (
                "Hiệu suất sạc nội bộ theo loại sạc",
                "bar",
                "SELECT charger_type, round(avg(avg_power_kw), 1) AS avg_power_kw, round(avg(charge_efficiency_pct), 1) AS avg_efficiency_pct FROM mart_charging_analytics GROUP BY 1",
                {},
            ),
        ],
    },
    # ------------------------------------------------------------- Dashboard 1 ----------
    {
        "name": "Customer 360 — Chân dung khách hàng",
        "description": "Mart: mart_customer_360 — Phân tích vòng đời, khu vực, chi tiêu, tương tác và tỷ lệ chuyển đổi",
        "kpis": [
            ("Tổng khách hàng", "SELECT count() AS customers FROM mart_customer_360"),
            ("Tổng chi tiêu (tỷ VND)", "SELECT round(sum(total_spent_vnd) / 1e9, 2) AS total_spent_bn_vnd FROM mart_customer_360"),
            ("Đơn hàng TB / khách", "SELECT round(avg(order_count), 1) AS avg_orders_per_customer FROM mart_customer_360"),
        ],
        "cards": [
            (
                "Phân bổ Lifecycle Stage",
                "pie",
                "SELECT lifecycle_stage, count() AS customers FROM mart_customer_360 GROUP BY 1 ORDER BY 2 DESC",
                {"pie.show_legend": True},
            ),
            (
                "Khách hàng theo thành phố",
                "bar",
                "SELECT city_code, count(customer_id) AS customers FROM mart_customer_360 GROUP BY 1 ORDER BY 2 DESC",
                {},
            ),
            (
                "Phân bổ trạng thái khách hàng",
                "pie",
                "SELECT status, count() AS customers FROM mart_customer_360 GROUP BY 1 ORDER BY 2 DESC",
                {"pie.show_legend": True},
            ),
            (
                "Top 10 khách hàng theo chi tiêu (triệu VND)",
                "bar",
                "SELECT name, round(total_spent_vnd / 1e6, 1) AS spent_m_vnd FROM mart_customer_360 ORDER BY total_spent_vnd DESC LIMIT 10",
                {},
            ),
            (
                "Tương tác vs Chi tiêu",
                "scatter",
                "SELECT interaction_count, total_spent_vnd FROM mart_customer_360",
                {
                    "graph.dimensions": ["interaction_count"],
                    "graph.metrics": ["total_spent_vnd"],
                    "graph.x_axis.scale": "linear",
                },
            ),
            (
                "Khách hàng mới theo tháng",
                "area",
                "SELECT date_trunc('month', registered_at) AS month, count() AS new_customers FROM mart_customer_360 GROUP BY 1 ORDER BY 1",
                {},
            ),
            (
                "Chuyển đổi Test Drive → Mua hàng",
                "funnel",
                "SELECT 'Test drive' AS stage, countIf(test_drive_count > 0) AS customers FROM mart_customer_360 "
                "UNION ALL SELECT 'Mua hàng', countIf(order_count > 0) FROM mart_customer_360",
                {},
            ),
            (
                "Khách hàng vs Số đại lý theo thành phố",
                "bar",
                "SELECT c.city_code, count(DISTINCT c.customer_id) AS customers, count(DISTINCT s.dealer_id) AS dealers "
                "FROM mart_customer_360 c LEFT JOIN mart_sales_pipeline s ON c.city_code = s.city_code GROUP BY 1 ORDER BY 2 DESC",
                {},
            ),
            (
                "Tỉ lệ chuyển đổi vs Doanh thu đại lý theo TP",
                "bar",
                "SELECT c.city_code, round(countIf(c.order_count > 0) * 100.0 / count(), 1) AS conversion_pct, "
                "round(sum(s.total_revenue_vnd) / 1e9, 2) AS dealer_revenue_bn "
                "FROM mart_customer_360 c LEFT JOIN mart_sales_pipeline s ON c.city_code = s.city_code GROUP BY 1",
                {},
            ),
        ],
    },
    # ------------------------------------------------------------- Dashboard 2 ----------
    {
        "name": "Sales Pipeline — Kênh bán hàng",
        "description": "Mart: mart_sales_pipeline — Doanh thu đại lý, phân bổ địa lý, cơ cấu ô tô/xe máy",
        "kpis": [
            ("Tổng doanh thu (tỷ VND)", "SELECT round(sum(total_revenue_vnd) / 1e9, 2) AS revenue_bn_vnd FROM mart_sales_pipeline"),
            ("Tổng đơn hàng", "SELECT sum(order_count) AS total_orders FROM mart_sales_pipeline"),
        ],
        "cards": [
            (
                "Top đại lý theo doanh thu (tỷ VND)",
                "bar",
                "SELECT dealer_name, round(total_revenue_vnd / 1e9, 2) AS revenue_bn_vnd FROM mart_sales_pipeline ORDER BY total_revenue_vnd DESC",
                {},
            ),
            (
                "Doanh thu theo thành phố (tỷ VND)",
                "bar",
                "SELECT city_code, round(sum(total_revenue_vnd) / 1e9, 2) AS revenue_bn_vnd FROM mart_sales_pipeline GROUP BY 1 ORDER BY 2 DESC",
                {},
            ),
            (
                "Car vs Bike theo đại lý",
                "bar",
                "SELECT dealer_name, car_orders, bike_orders FROM mart_sales_pipeline ORDER BY total_revenue_vnd DESC",
                {"stackable.stack_type": "stacked"},
            ),
            (
                "Phân bổ loại đại lý",
                "pie",
                "SELECT dealer_type, count() AS dealers FROM mart_sales_pipeline GROUP BY 1 ORDER BY 2 DESC",
                {"pie.show_legend": True},
            ),
            (
                "Giá trị đơn hàng trung bình (triệu VND)",
                "bar",
                "SELECT dealer_name, round(avg_order_value_vnd / 1e6, 1) AS aov_m_vnd FROM mart_sales_pipeline ORDER BY avg_order_value_vnd DESC",
                {},
            ),
            (
                "Số ngày hoạt động của đại lý",
                "bar",
                "SELECT dealer_name, dateDiff('day', "
                "parseDateTimeBestEffort(substring(toString(assumeNotNull(first_sale_at)), 1, 19)), "
                "parseDateTimeBestEffort(substring(toString(assumeNotNull(last_sale_at)), 1, 19))) AS active_days "
                "FROM mart_sales_pipeline WHERE toString(first_sale_at) != '' ORDER BY active_days DESC",
                {},
            ),
        ],
    },
    # ------------------------------------------------------------- Dashboard 3 ----------
    {
        "name": "Charging Revenue — Doanh thu trạm sạc ngoài",
        "description": "Mart: mart_charging_revenue — Thống kê doanh thu, sản lượng kWh và lượt sạc mạng ngoài OCPP",
        "kpis": [
            ("Tổng doanh thu (triệu VND)", "SELECT round(sum(total_revenue_vnd) / 1e6, 1) AS revenue_m_vnd FROM mart_charging_revenue"),
            ("Tổng kWh", "SELECT round(sum(total_kwh), 1) AS total_kwh FROM mart_charging_revenue"),
            ("Tổng phiên sạc", "SELECT sum(session_count) AS total_sessions FROM mart_charging_revenue"),
        ],
        "cards": [
            (
                "Doanh thu theo trạm (triệu VND)",
                "bar",
                "SELECT station_id, round(total_revenue_vnd / 1e6, 1) AS revenue_m_vnd FROM mart_charging_revenue ORDER BY total_revenue_vnd DESC",
                {},
            ),
            (
                "AC vs DC — doanh thu & kWh",
                "bar",
                "SELECT charger_type, round(sum(total_revenue_vnd) / 1e6, 1) AS revenue_m_vnd, round(sum(total_kwh), 1) AS total_kwh FROM mart_charging_revenue GROUP BY 1",
                {},
            ),
            (
                "Số phiên sạc theo trạm",
                "bar",
                "SELECT station_id, session_count FROM mart_charging_revenue ORDER BY session_count DESC",
                {},
            ),
            (
                "Avg kWh / phiên theo trạm",
                "bar",
                "SELECT station_id, round(avg_kwh, 1) AS avg_kwh FROM mart_charging_revenue ORDER BY avg_kwh DESC",
                {},
            ),
            (
                "Doanh thu trạm vs Thời lượng sạc TB (nội bộ)",
                "bar",
                "SELECT r.station_id, round(r.total_revenue_vnd / 1e6, 1) AS revenue_m_vnd, "
                "round(avg(a.duration_min), 1) AS avg_duration_min "
                "FROM mart_charging_revenue r JOIN mart_charging_analytics a ON r.station_id = a.station_id "
                "GROUP BY r.station_id, r.total_revenue_vnd ORDER BY 2 DESC",
                {},
            ),
            (
                "Hiệu quả trạm: doanh thu / phiên vs kWh / phiên",
                "bar",
                "SELECT station_id, round(total_revenue_vnd / nullIf(session_count, 0) / 1e3, 1) AS revenue_per_session_k, "
                "round(avg_kwh, 1) AS avg_kwh FROM mart_charging_revenue ORDER BY 2 DESC",
                {},
            ),
        ],
    },
    # ------------------------------------------------------------- Dashboard 4 ----------
    {
        "name": "Charging Analytics — Hiệu suất phiên sạc",
        "description": "Mart: mart_charging_analytics — Phân tích thời lượng sạc, biến động SOC, công suất và chi phí sạc nội bộ",
        "kpis": [
            ("Thời lượng sạc TB (phút)", "SELECT round(avg(duration_min), 1) AS avg_duration_min FROM mart_charging_analytics"),
            ("Giá TB / kWh (VND)", "SELECT round(avg(cost_per_kwh_vnd), 0) AS avg_cost_per_kwh FROM mart_charging_analytics"),
            ("Hiệu suất sạc TB (%)", "SELECT round(avg(charge_efficiency_pct), 1) AS avg_efficiency_pct FROM mart_charging_analytics"),
        ],
        "cards": [
            (
                "Phân bổ thời lượng sạc (bucket 15 phút)",
                "bar",
                "SELECT concat(toString(bucket), '-', toString(bucket + 15), ' phút') AS duration_bucket, sessions FROM ("
                "SELECT intDiv(toUInt32(duration_min), 15) * 15 AS bucket, count() AS sessions "
                "FROM mart_charging_analytics GROUP BY 1"
                ") ORDER BY bucket",
                {"graph.dimensions": ["duration_bucket"]},
            ),
            (
                "SOC vào vs SOC ra",
                "scatter",
                "SELECT start_soc_pct, end_soc_pct FROM mart_charging_analytics",
                {
                    "graph.dimensions": ["start_soc_pct"],
                    "graph.metrics": ["end_soc_pct"],
                    "graph.x_axis.scale": "linear",
                },
            ),
            (
                "Fast vs Slow charge",
                "pie",
                "SELECT if(is_fast_charge, 'Fast (DC)', 'Slow (AC)') AS charge_mode, count() AS sessions FROM mart_charging_analytics GROUP BY 1",
                {"pie.show_legend": True},
            ),
            (
                "Công suất TB theo model xe (kW)",
                "bar",
                "SELECT model, round(avg(avg_power_kw), 1) AS avg_power_kw FROM mart_charging_analytics GROUP BY 1 ORDER BY 2 DESC",
                {},
            ),
            (
                "Phiên sạc theo giờ trong ngày",
                "bar",
                "SELECT concat(toString(h), ':00') AS hour_of_day, sessions FROM ("
                "SELECT toHour(started_at) AS h, count() AS sessions FROM mart_charging_analytics GROUP BY 1"
                ") ORDER BY h",
                {"graph.dimensions": ["hour_of_day"]},
            ),
            (
                "Chi phí theo phương thức thanh toán (triệu VND)",
                "pie",
                "SELECT payment_method, round(sum(cost_vnd) / 1e6, 1) AS cost_m_vnd FROM mart_charging_analytics GROUP BY 1 ORDER BY 2 DESC",
                {"pie.show_legend": True},
            ),
            (
                "Hiệu suất sạc TB theo model (%)",
                "bar",
                "SELECT model, round(avg(charge_efficiency_pct), 1) AS avg_efficiency_pct FROM mart_charging_analytics GROUP BY 1 ORDER BY 2 DESC",
                {},
            ),
            (
                "Trend phiên sạc theo ngày",
                "line",
                "SELECT toDate(started_at) AS day, count() AS sessions FROM mart_charging_analytics GROUP BY 1 ORDER BY 1",
                {},
            ),
        ],
    },
    # ------------------------------------------------------------- Dashboard 5 ----------
    {
        "name": "Vehicle 360 — Chân dung phương tiện",
        "description": "Mart: mart_vehicle_360 — Phân bổ dòng xe, khu vực, trạng thái chai pin (SoH), các sự kiện cảnh báo",
        "kpis": [
            ("SoH pin TB (%)", "SELECT round(avg(current_soh_pct), 1) AS avg_soh_pct FROM mart_vehicle_360"),
            ("Tổng kWh sạc", "SELECT round(sum(total_kwh_charged), 1) AS total_kwh FROM mart_vehicle_360"),
            ("Tổng số xe", "SELECT count() AS vehicles FROM mart_vehicle_360"),
        ],
        "cards": [
            (
                "Phân bổ xe theo model",
                "pie",
                "SELECT model, count(vehicle_id) AS vehicles FROM mart_vehicle_360 GROUP BY 1 ORDER BY 2 DESC",
                {"pie.show_legend": True},
            ),
            (
                "Xe theo thành phố",
                "bar",
                "SELECT city_code, count(vehicle_id) AS vehicles FROM mart_vehicle_360 GROUP BY 1 ORDER BY 2 DESC",
                {},
            ),
            (
                "Phân bổ SoH pin (%)",
                "bar",
                "SELECT concat(toString(bucket), '%') AS soh_bucket, vehicles FROM ("
                "SELECT round(current_soh_pct, 0) AS bucket, count() AS vehicles FROM mart_vehicle_360 GROUP BY 1"
                ") ORDER BY bucket",
                {"graph.dimensions": ["soh_bucket"]},
            ),
            (
                "SoC trung bình theo model (%)",
                "bar",
                "SELECT model, round(avg(lifetime_avg_soc_pct), 1) AS avg_soc_pct FROM mart_vehicle_360 GROUP BY 1 ORDER BY 2 DESC",
                {},
            ),
            (
                "Top 10 xe theo tổng km",
                "bar",
                "SELECT vehicle_id, round(total_distance_km) AS distance_km FROM mart_vehicle_360 ORDER BY total_distance_km DESC LIMIT 10",
                {},
            ),
            (
                "Xe có cảnh báo theo model (lốp / nhiệt pin)",
                "bar",
                "SELECT model, countIf(had_tire_pressure_alert) AS tire_alerts, countIf(had_battery_temp_alert) AS temp_alerts FROM mart_vehicle_360 GROUP BY 1",
                {"stackable.stack_type": "stacked"},
            ),
            (
                "Phiên sạc vs Quãng đường",
                "scatter",
                "SELECT total_charging_sessions, total_distance_km FROM mart_vehicle_360",
                {
                    "graph.dimensions": ["total_charging_sessions"],
                    "graph.metrics": ["total_distance_km"],
                    "graph.x_axis.scale": "linear",
                },
            ),
            (
                "SoH pin vs Hiệu suất sạc TB",
                "scatter",
                "SELECT v.current_soh_pct, round(avg(a.charge_efficiency_pct), 1) AS avg_efficiency_pct "
                "FROM mart_vehicle_360 v JOIN mart_charging_analytics a ON v.vehicle_id = a.vehicle_id "
                "GROUP BY v.vehicle_id, v.current_soh_pct",
                {
                    "graph.dimensions": ["current_soh_pct"],
                    "graph.metrics": ["avg_efficiency_pct"],
                    "graph.x_axis.scale": "linear",
                },
            ),
            (
                "Tiêu hao năng lượng: kWh / 100km theo model",
                "bar",
                "SELECT v.model, round(sum(a.kwh_delivered) / nullIf(max(v.total_distance_km), 0) * 100, 2) AS kwh_per_100km "
                "FROM mart_vehicle_360 v JOIN mart_charging_analytics a ON v.vehicle_id = a.vehicle_id "
                "GROUP BY 1 ORDER BY 2 DESC",
                {},
            ),
            (
                "Xe có cảnh báo → chi phí sạc cao hơn?",
                "bar",
                "SELECT if(v.had_battery_temp_alert OR v.had_tire_pressure_alert, 'Có cảnh báo', 'Không cảnh báo') AS alert_group, "
                "round(avg(a.cost_per_kwh_vnd), 0) AS avg_cost_per_kwh "
                "FROM mart_vehicle_360 v JOIN mart_charging_analytics a ON v.vehicle_id = a.vehicle_id GROUP BY 1",
                {},
            ),
        ],
    },
    # ------------------------------------------------------------- Dashboard 6 ----------
    {
        "name": "Daily Fleet — Vận hành đội xe theo ngày",
        "description": "Mart: mart_daily_fleet — Số lượng xe hoạt động, tổng km di chuyển, chỉ số sạc và cảnh báo theo ngày",
        "kpis": [
            ("Xe hoạt động TB / ngày", "SELECT round(avg(active_vehicles), 1) AS avg_active_vehicles FROM mart_daily_fleet"),
            ("Tổng chuyến đi", "SELECT sum(total_trips) AS total_trips FROM mart_daily_fleet"),
            ("Tổng kWh sạc", "SELECT round(sum(total_kwh_charged), 1) AS total_kwh FROM mart_daily_fleet"),
        ],
        "cards": [
            (
                "Xe hoạt động theo ngày",
                "line",
                "SELECT activity_date, active_vehicles FROM mart_daily_fleet ORDER BY 1",
                {},
            ),
            (
                "Tổng km theo ngày",
                "area",
                "SELECT activity_date, round(total_distance_km) AS distance_km FROM mart_daily_fleet ORDER BY 1",
                {},
            ),
            (
                "Tổng chuyến đi theo ngày",
                "bar",
                "SELECT activity_date, total_trips FROM mart_daily_fleet ORDER BY 1",
                {},
            ),
            (
                "kWh sạc theo ngày",
                "area",
                "SELECT activity_date, round(total_kwh_charged, 1) AS kwh_charged FROM mart_daily_fleet ORDER BY 1",
                {},
            ),
            (
                "Fleet SoC trung bình theo ngày (%)",
                "line",
                "SELECT activity_date, round(avg_fleet_soc_pct, 1) AS avg_soc_pct FROM mart_daily_fleet ORDER BY 1",
                {},
            ),
            (
                "Cảnh báo lốp & nhiệt pin theo ngày",
                "line",
                "SELECT activity_date, vehicles_with_tire_alert, vehicles_with_temp_alert FROM mart_daily_fleet ORDER BY 1",
                {},
            ),
            (
                "Tương quan: xe hoạt động vs phiên sạc theo ngày",
                "bar",
                "SELECT f.activity_date, f.active_vehicles, count(a.session_id) AS charging_sessions "
                "FROM mart_daily_fleet f LEFT JOIN mart_charging_analytics a ON f.activity_date = toDate(a.started_at) "
                "GROUP BY 1, 2 ORDER BY 1",
                {},
            ),
            (
                "km đi vs kWh sạc theo ngày (dual metric)",
                "line",
                "SELECT activity_date, round(total_distance_km) AS distance_km, round(total_kwh_charged, 1) AS kwh_charged "
                "FROM mart_daily_fleet ORDER BY 1",
                {},
            ),
        ],
    },
]


def _cleanup_old(base_url: str, headers: dict[str, str], coll_id: int) -> None:
    """Xóa các Dashboard và Card trùng tên trong Collection để đảm bảo tính định đề (Idempotency)."""
    items = requests.get(
        f"{base_url}/api/collection/{coll_id}/items",
        headers=headers,
        params={"models": ["dashboard", "card"]},
        timeout=10,
    ).json()

    managed_names = (
        {d["name"] for d in DASHBOARDS}
        | {c[0] for d in DASHBOARDS for c in d["cards"]}
        | {k[0] for d in DASHBOARDS for k in d.get("kpis", [])}
    )

    for item in items.get("data", []):
        if item.get("name") in managed_names:
            item_id = item["id"]
            if item.get("model") == "dashboard":
                requests.put(
                    f"{base_url}/api/dashboard/{item_id}",
                    headers=headers,
                    json={"archived": True},
                    timeout=10,
                )
                requests.delete(f"{base_url}/api/dashboard/{item_id}", headers=headers, timeout=10)
                print(f"  - Xóa Dashboard cũ: '{item['name']}'")
            else:
                requests.put(
                    f"{base_url}/api/card/{item_id}",
                    headers=headers,
                    json={"archived": True},
                    timeout=10,
                )
                requests.delete(f"{base_url}/api/card/{item_id}", headers=headers, timeout=10)
                print(f"  - Xóa Card cũ: '{item['name']}'")


def _create_card(
    base_url: str,
    headers: dict[str, str],
    coll_id: int,
    db_id: int,
    name: str,
    display: str,
    sql: str,
    viz: dict[str, Any],
) -> int:
    """Tạo mới một Card biểu đồ trong Metabase qua API."""
    response = requests.post(
        f"{base_url}/api/card",
        headers=headers,
        json={
            "name": name,
            "display": display,
            "collection_id": coll_id,
            "dataset_query": {"database": db_id, "type": "native", "native": {"query": sql}},
            "visualization_settings": viz or {},
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["id"]


def _get_or_create_collection(base_url: str, headers: dict[str, str]) -> int:
    """Tìm hoặc tạo mới Collection 'VinFast' chứa tất cả các Dashboard."""
    colls = requests.get(f"{base_url}/api/collection", headers=headers, timeout=10).json()

    for c in colls:
        if c.get("name") == "VinFast" and not c.get("archived") and c.get("personal_owner_id") is None:
            return c["id"]

    response = requests.post(
        f"{base_url}/api/collection",
        headers=headers,
        json={
            "name": "VinFast",
            "color": "#509EE3",
            "description": "Dashboard nền tảng dữ liệu VinFast EV",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["id"]


def build_dashboards(base_url: str, headers: dict[str, str], db_id: int) -> list[int]:
    """Tạo toàn bộ danh sách Dashboards và Cards trong Metabase."""
    coll_id = _get_or_create_collection(base_url, headers)
    print(f"Collection ID = {coll_id}")

    _cleanup_old(base_url, headers, coll_id)

    dash_ids: list[int] = []
    for spec in DASHBOARDS:
        response = requests.post(
            f"{base_url}/api/dashboard",
            headers=headers,
            json={"name": spec["name"], "description": spec["description"], "collection_id": coll_id},
            timeout=10,
        )
        response.raise_for_status()
        dash_id = response.json()["id"]
        print(f"Dashboard '{spec['name']}' ID = {dash_id}")

        dash_cards: list[dict[str, Any]] = []

        # 1. Bố cục các thẻ KPI (Scorecards): kích thước 4x2, 3 card/hàng
        kpis = spec.get("kpis", [])
        kpi_rows = (len(kpis) + 2) // 3

        for i, (name, sql) in enumerate(kpis):
            card_id = _create_card(base_url, headers, coll_id, db_id, name, "scalar", sql, {})
            dash_cards.append(
                {
                    "id": card_id,
                    "card_id": card_id,
                    "col": (i % 3) * 4,
                    "row": (i // 3) * 2,
                    "size_x": 4,
                    "size_y": 2,
                    "visualization_settings": {},
                }
            )
            print(f"  + KPI '{name}' (ID = {card_id})")

        # 2. Bố cục các thẻ biểu đồ (Charts Grid): kích thước 6x4, xếp 2 cột
        chart_start_row = kpi_rows * 2 + 1
        for i, (name, display, sql, viz) in enumerate(spec["cards"]):
            card_id = _create_card(base_url, headers, coll_id, db_id, name, display, sql, viz)
            col = (i % 2) * 6
            row = chart_start_row + (i // 2) * 4

            dash_cards.append(
                {
                    "id": card_id,
                    "card_id": card_id,
                    "col": col,
                    "row": row,
                    "size_x": 6,
                    "size_y": 4,
                    "visualization_settings": viz or {},
                }
            )
            print(f"  + Card '{name}' (ID = {card_id})")

        # Gắn danh sách Cards vào Dashboard
        res_attach = requests.put(
            f"{base_url}/api/dashboard/{dash_id}/cards",
            headers=headers,
            json={"cards": dash_cards},
            timeout=30,
        )
        res_attach.raise_for_status()
        print(f"  = Gắn {len(dash_cards)} thẻ vào Dashboard '{spec['name']}'")
        dash_ids.append(dash_id)

    return dash_ids


def main() -> None:
    """Hàm thực thi chính của Script khởi tạo Metabase Dashboards."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BASE_URL, help="Đường dẫn URL của Metabase API")
    args = parser.parse_args()
    base_url = args.base_url

    wait_metabase(base_url)
    setup_admin(base_url)
    headers = login(base_url)
    db_id = add_clickhouse(base_url, headers)
    dash_ids = build_dashboards(base_url, headers, db_id)

    print("\nHoàn tất thiết lập Metabase Dashboards:")
    for did in dash_ids:
        print(f"  - {base_url}/dashboard/{did}")


if __name__ == "__main__":
    main()
