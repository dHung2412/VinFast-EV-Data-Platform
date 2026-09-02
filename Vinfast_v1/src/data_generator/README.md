# Hệ Thống Mô Phỏng Dữ Liệu Xe Điện VinFast (Data Generator)

Tài liệu này trình bày tổng quan cấu trúc dữ liệu, mối liên kết liên nguồn (Cross-Source Linkage) và cơ chế tác động qua lại giữa các tập dữ liệu mô phỏng thuộc module `src/data_generator`.

---

## 1. Cấu Trúc Tổng Quan Các Tập Dữ Liệu

Hệ thống mô phỏng sinh ra 3 nhóm dữ liệu chính phục vụ cho Data Pipeline:

```
+-----------------------------------------------------------------------------------+
|                                1. DỮ LIỆU THỰC THỂ (Entities)                      |
|  - Users (users.parquet): Thông tin tài khoản người dùng ứng dụng                 |
|  - Vehicles (vehicles.parquet): Thông số kỹ thuật & thông số khởi tạo xe          |
|  - Stations (stations.parquet): Vị trí & thông số kỹ thuật các trạm sạc          |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                                2. DỮ LIỆU TELEMETRY & PHIÊN SẠC                   |
|  - Telemetry (telemetry/year=/month=/day=/): Chuỗi thời gian cảm biến xe          |
|  - Charging Sessions (charging_sessions/): Phiên sạc trích xuất từ Telemetry      |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                                3. DỮ LIỆU GIẢ LẬP THÔ (Mock Raw CSVs)              |
|  - CRM (data/raw/crm/): Khách hàng (customer.csv), Tương tác (interaction.csv)     |
|  - DMS (data/raw/dms/): Đại lý (dealer.csv), Đơn hàng (sales_order.csv), Tồn kho  |
|  - Charging External (data/raw/charging/): Phiên sạc đối tác (charging_session.csv)|
+-----------------------------------------------------------------------------------+
```

---

## 2. Chi Tiết Các Thực Thể & Bảng Dữ Liệu

### 2.1. Nhóm Thực Thể Tĩnh (Entities)

1. **Người dùng ứng dụng (`users.parquet`):**
   * **Các trường:** `u_id` (Mã người dùng), `name` (Họ tên), `phone` (Số điện thoại liên hệ).
   * **Quy tắc tác động:** Một người dùng có thể sở hữu từ 1 đến 3 phương tiện (xác suất 80% sở hữu 1 xe, 15% sở hữu 2 xe, 5% sở hữu 3 xe).

2. **Phương tiện (`vehicles.parquet`):**
   * **Các trường:** `vehicle_id`, `u_id`, `model`, `type` (`car` / `motorbike`), `city_code`, `home_lat`, `home_lon`, `work_lat`, `work_lon`, `battery_kwh`, `wh_per_km`, `mass_kg`, `Cd`, `A_frontal_m2`, `r_wheel_m`, `gear_ratio`, `V_pack_nom_v`, `R_int_base_ohm`, `odometer_start_km`, `tire_pressure_base_bar`, `battery_soh_pct`, `years_old`.
   * **Quy tắc tác động:** Các thông số vật lý tĩnh (`mass_kg`, `Cd`, `A_frontal_m2`, `battery_kwh`) trực tiếp quyết định lực cản, mức tiêu thụ năng lượng và tốc độ chai pin của xe khi vận hành.

3. **Trạm sạc VinFast (`stations.parquet`):**
   * **Các trường:** `station_id`, `city_code`, `charger_type` (`AC_TYPE2` / `CCS2_DC`), `max_power_kw`, `num_chargers`, `lat`, `lon`.
   * **Quy tắc tác động:** Loại cổng sạc và công suất tối đa quyết định tốc độ nạp pin và chi phí sạc điện.

### 2.2. Nhóm Dữ Liệu Chuỗi Thời Gian Telemetry (`telemetry`)

Tập dữ liệu chuỗi thời gian ghi nhận cảm biến xe theo chu kỳ:
* **Khi lái xe:** Lấy mẫu định kỳ 10 giây/mẫu (`SAMPLE_SECONDS_DRIVING = 10`).
* **Khi sạc pin:** Lấy mẫu định kỳ 60 giây/mẫu (`SAMPLE_SECONDS_CHARGING = 60`).
* **Khi dừng đỗ (Parked/Idle):** Lấy mẫu nhịp tim định kỳ 15 phút/mẫu (Heartbeat).

| Nhóm dữ liệu | Các thuộc tính | Mô tả & Tác động vật lý |
| :--- | :--- | :--- |
| **Định danh & Thời gian** | `vehicle_id`, `u_id`, `model`, `type`, `event_timestamp` | Mã định danh xe, chủ sở hữu và mốc thời gian chuẩn UTC. |
| **Hệ thống Pin** | `battery_soc_pct`, `battery_soh_pct`, `battery_temp_c`, `battery_temp_avg_c`, `battery_temp_max_c`, `charging_status` | Dung lượng pin %, độ khỏe %, nhiệt độ pin và trạng thái sạc. Mức pin giảm làm giảm điện áp hở mạch $V_{\text{ocv}}$, gây tăng dòng điện $I$ và tăng nhiệt Joule $I^2 R_{\text{int}}$. |
| **Vận hành & Truyền động** | `speed_kmh`, `odometer_km`, `motor_rpm`, `motor_temp_c`, `inverter_temp_c`, `gear_mode` | Vận tốc, quãng đường ODO, tốc độ quay động cơ, nhiệt độ động cơ/bộ biến tần và chế độ số (`P`, `D`, `B`). |
| **Định vị & IMU** | `latitude`, `longitude`, `acceleration_x`, `acceleration_y`, `acceleration_z` | Tọa độ GPS và gia tốc 3 trục. Gia tốc dọc $a_x$ kéo dài $> 35 m/s^2$ sẽ kích hoạt sự kiện túi khí. |
| **Thân xe & Khung gầm** | `lock_status`, `cabin_temp_c`, `hvac_power_kw`, `airbag_deployed`, `tire_pressure_fl/fr/rl/rr_bar` | Trạng thái khóa cửa, nhiệt độ cabin, công suất điều hòa và áp suất 4 lốp. Nhiệt độ môi trường và vận tốc xe làm dãn nở áp suất lốp. |
| **Môi trường & Sạc** | `ambient_temp_c`, `is_charging`, `charging_power_kw`, `ignition_on` | Nhiệt độ môi trường biến thiên dạng cosin, cờ trạng thái sạc và trạng thái khóa điện. |

### 2.3. Nhóm Dữ Liệu Nghiệp Vụ (CRM, DMS, External Charging)

1. **Hệ thống CRM (`data/raw/crm/`):**
   * **Khách hàng (`customer.csv`):** `customer_code`, `full_name`, `phone_number`, `email`, `customer_status`, `registered_date`, `city`.
   * **Tương tác (`interaction.csv`):** `interaction_id`, `phone_number`, `interaction_type`, `interaction_date`, `outcome`, `agent_name`, `notes`.

2. **Hệ thống DMS đại lý (`data/raw/dms/`):**
   * **Đại lý (`dealer.csv`):** `dealer_code`, `dealer_name`, `city`, `address`, `lat`, `lon`, `dealer_type`.
   * **Đơn hàng bán xe (`sales_order.csv`):** `order_id`, `vin`, `dealer_code`, `customer_phone`, `sale_date`, `model_code`, `color`, `unit_price_vnd`, `payment_method`, `warranty_start`.
   * **Tồn kho (`inventory.csv`):** `vin`, `model_code`, `color`, `dealer_code`, `stock_in_date`, `status`.

3. **Hệ thống Sạc bên ngoài (`data/raw/charging/`):**
   * **Phiên sạc đối tác (`charging_session.csv`):** `session_id`, `vin`, `station_id`, `connector_id`, `charger_type`, `started_at`, `ended_at`, `kwh_delivered`, `cost_vnd`, `payment_method`.

---

## 3. Mối Liêu Kết & Tác Động Liên Nguồn (Cross-Source Inter-dependencies)

Sơ đồ thể hiện luồng liên kết dữ liệu giữa các nguồn:

```
+------------------------+             +------------------------+
|    Hệ Thống CRM        |             |    Ứng Dụng VinFast    |
|   (customer.csv)       |             |    (users.parquet)     |
|   - phone_number  <----+-------------+---> - phone            |
+-----------+------------+ (Match 85%) +-----------+------------+
            |                                      |
            v (Match 100%)                         v (Match 100%)
+-----------+------------+             +-----------+------------+
|    Hệ Thống DMS        |             |     Đội Xe VinFast       |
|  (sales_order.csv)     |             |   (vehicles.parquet)   |
|  - customer_phone      |             |   - u_id               |
|  - vin                 |             |   - vehicle_id         |
+-----------+------------+             +-----------+------------+
            |                                      |
            v (Match 85%)                          v (Single Source of Truth)
+-----------+------------+             +-----------+------------+
|  Sạc Ngoài External    |             |    Dữ Liệu Telemetry   |
| (charging_session.csv) |             |  (telemetry/ is_charging)|
|  - vin                 |             +-----------+------------+
+------------------------+                         |
                                                   v (Trích xuất tự động)
                                       +------------------------+
                                       |   Charging Sessions    |
                                       |  (charging_sessions/)  |
                                       +------------------------+
```

### 3.1. Liên kết Khách hàng CRM $\leftrightarrow$ Người dùng App (`phone_number`)
* **Cơ chế:** Số điện thoại `phone_number` của khách hàng trong hệ thống CRM được liên kết với số điện thoại `phone` của người dùng tài khoản ứng dụng VinFast với tỷ lệ đồng bộ 85%.
* **Tác động:** Cho phép đối soát thông tin cá nhân khách hàng giữa hệ thống bán hàng/chăm sóc khách hàng và tài khoản định danh trên ứng dụng di động.

### 3.2. Liên kết Đơn hàng DMS $\leftrightarrow$ Khách hàng CRM & Xe điện (`vin` & `phone`)
* **Cơ chế:** Đơn hàng bán xe trong DMS ghi nhận mã số `vin` duy nhất và số điện thoại `customer_phone` của người mua.
* **Tác động:** 100% số điện thoại người mua trên đơn hàng bán xe DMS tồn tại trong tập dữ liệu khách hàng CRM, đảm bảo tính toàn vẹn dữ liệu từ khâu tư vấn bán hàng đến giao xe.

### 3.3. Liên kết Sạc ngoài $\leftrightarrow$ Đơn hàng DMS (`vin`)
* **Cơ chế:** 85% các phiên sạc pin tại trạm sạc bên ngoài (`charging_session.csv`) ghi nhận mã `vin` của các xe đã được bán ra từ đơn hàng DMS. 15% còn lại là các lượt sạc vãng lai hoặc để trống mã VIN.
* **Tác động:** Cho phép phân tích tần suất sạc pin của từng xe cụ thể tại các hệ thống trạm sạc đối tác ngoài VinFast.

### 3.4. Telemetry $\rightarrow$ Phiên sạc trích xuất (`charging_sessions`)
* **Cơ chế:** Dữ liệu chuỗi thời gian Telemetry là **Nguồn dữ liệu gốc duy nhất (Single Source of Truth)**. Khi thuộc tính `is_charging == True` kéo dài liên tục, thuật toán tự động trích xuất phân đoạn đó thành một phiên sạc chuẩn.
* **Tác động:** 
  * Thời lượng sạc (`duration_min`) = Khoảng thời gian từ lúc cắm sạc đến khi rút sạc.
  * Mức pin đầu/cuối (`start_soc_pct`, `end_soc_pct`) được lấy từ giá trị `battery_soc_pct` thực tế của cảm biến pin.
  * Tổng điện năng nạp (`kwh_delivered`) được tích phân từ công suất sạc `charging_power_kw` theo thời gian.
  * Chi phí sạc (`cost_vnd`) tính theo giá niêm yết của loại cổng sạc và tự động nhân hệ số **1.2** trong khung giờ cao điểm (17h00 - 21h00) đối với sạc nhanh DC.

---

## 4. Hướng Dẫn Sử Dụng Công Cụ Dòng Lệnh (CLI Command)

Tệp [cli.py](file:///d:/Project/Data_Engineering/Vinfast_v1/src/data_generator/cli.py) cung cấp 2 lệnh chính để sinh dữ liệu:

### 4.1. Lệnh sinh dữ liệu mô phỏng tổng hợp (`generate`)
```bash
python -m src.data_generator.cli generate \
    --start-date 2026-01-01 \
    --end-date 2026-01-07 \
    --vehicles 20 \
    --seed 42 \
    --output data/raw \
    --datasets all
```
* `--start-date` & `--end-date`: Khoảng thời gian mô phỏng dữ liệu chuỗi thời gian.
* `--vehicles`: Số lượng phương tiện cần sinh trong đội xe.
* `--datasets`: Chọn các tập dữ liệu cần sinh (`telemetry`, `charging_sessions`, `users`, `vehicles`, `stations`, hoặc `all`).

### 4.2. Lệnh sinh dữ liệu thô nghiệp vụ CSV (`mock-raw`)
```bash
python -m src.data_generator.cli mock-raw \
    --source all \
    --seed 42 \
    --n-customers 40
```
* `--source`: Chọn nguồn dữ liệu cần tạo (`crm`, `dms`, `charging`, hoặc `all`).
* `--n-customers`: Số lượng bản ghi khách hàng CRM.
