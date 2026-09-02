# Hướng Dẫn Tầng Xử Lý Dữ Liệu Tự Động (Metadata-Driven Pipeline Framework)

Tầng pipeline của hệ thống thực hiện luồng xử lý 6 bước tự động: trích xuất dữ liệu thô từ nhiều nguồn (CSV, Parquet, API, Kafka), kiểm định chất lượng theo Hợp đồng dữ liệu (Data Contract), chuẩn hóa cấu trúc trường, ánh xạ định danh thực thể liên nguồn và lưu trữ dữ liệu tầng Silver trên MinIO S3 (hoặc hệ thống tệp cục bộ dự phòng).

Tầng pipeline 6 bước: đọc raw từ nhiều nguồn (CSV/Parquet/API/Kafka), chuẩn hóa schema,
khớp identity xuyên nguồn, ghi Silver Parquet lên MinIO. **Nguồn mới = 1 YAML + 1 contract JSON, không code.**

## 1. Sơ Đồ Kiến Trúc Luồng Xử Lý 6 Bước

```
Extract ──► Validate ──► Land ──► Map ──► Resolve ──► Conform
(csv/      (Data        (Bronze    (Rename     (Identity      (Silver
 parquet    Contract     MinIO +    + Transform  SQLite         Parquet +
 hive)      QC Checks)   Metadata)  + Plugin)    3 Strategies)  Derived + Dedup)
```

| Bước xử lý | Module tương ứng | Vai trò và chức năng chính |
| :--- | :--- | :--- |
| **1. Extract** | [extractor.py](file:///d:/Project/Data_Engineering/Vinfast_v1/src/pipeline/extractor.py) | Trích xuất dữ liệu thô theo định dạng: CSV (tìm tệp theo ngày/thư mục), Parquet (phân vùng Hive `year=/month=/day=`). |
| **2. Validate** | [validator.py](file:///d:/Project/Data_Engineering/Vinfast_v1/src/pipeline/validator.py) | Kiểm định dữ liệu theo Data Contract: sự tồn tại cột, ràng buộc không Null và tính duy nhất của khóa chính (Primary Key Uniqueness). |
| **3. Land** | [lander.py](file:///d:/Project/Data_Engineering/Vinfast_v1/src/pipeline/lander.py) | Lưu trữ tầng Bronze tại MinIO (`s3://vinfast-bronze/<source>/<date>/`) kèm metadata (`_ingested_at`, `_source`, `_batch_id`, `_entity`). Khi MinIO không khả dụng, hệ thống tự động ghi vào `data/bronze/`. |
| **4. Map** | [mapper.py](file:///d:/Project/Data_Engineering/Vinfast_v1/src/pipeline/mapper.py) | Đổi tên trường nguồn sang trường chuẩn (`source -> canonical`) và biến đổi kiểu dữ liệu (`normalize_phone`, `parse_date`, `lower`, `upper`). |
| **5. Resolve** | [resolver.py](file:///d:/Project/Data_Engineering/Vinfast_v1/src/pipeline/resolver.py) | Tra cứu và giải quyết định danh thực thể liên nguồn (`source_keys -> canonical_id`) thông qua kho lưu trữ SQLite. |
| **6. Conform** | [conformer.py](file:///d:/Project/Data_Engineering/Vinfast_v1/src/pipeline/conformer.py) | Tính toán các cột phái sinh (`least()`, phép toán điều kiện, khoảng thời gian), loại bỏ trùng lặp (`dedup`) và xuất dữ liệu Silver Parquet (`pandas` hoặc `spark`). |

* **Bộ điều phối (Orchestrator):** [runner.py](file:///d:/Project/Data_Engineering/Vinfast_v1/src/pipeline/runner.py) thực thi tuần tự 6 bước cho từng thực thể.
* **Giao diện dòng lệnh (CLI):** [cli.py](file:///d:/Project/Data_Engineering/Vinfast_v1/src/pipeline/cli.py) nhận các tham số từ dòng lệnh.

---

## 2. Structure Cấu Trúc Mã Nguồn

```
src/pipeline/
├── cli.py              # Giao diện dòng lệnh: python -m src.pipeline.cli list|run
├── config_loader.py    # Nạp cấu hình YAML nguồn và Data Contract JSON
├── extractor.py        # Bước 1: Trích xuất dữ liệu CSV / Parquet
├── validator.py        # Bước 2: Kiểm định chất lượng theo Data Contract
├── lander.py           # Bước 3: Lưu trữ tầng Bronze MinIO + Metadata
├── mapper.py           # Bước 4: Đổi tên cột và chuyển đổi định dạng
├── resolver.py         # Bước 5: Giải quyết định danh theo 3 chiến lược
├── conformer.py        # Bước 6: Tính cột phái sinh, khử trùng lặp & lưu tầng Silver
├── identity_store.py   # Kho lưu trữ định danh SQLite & hàm sinh ID SHA256
├── runner.py           # Điều phối luồng 6 bước theo từng thực thể
├── gold.py             # Tổng hợp các Data Marts tầng Gold (Customer 360, Sales, Charging)
└── plugins/
    └── base.py         # Giao diện Plugin cơ sở (SourcePlugin): hooks pre_map / post_resolve / pre_conform
```

---

## 3. Hướng Dẫn Sử Dụng Dòng Lệnh (CLI Command)

```powershell
# 1. Liệt kê danh sách các nguồn dữ liệu khả dụng
python -m src.pipeline.cli list

# 2. Chạy thử nghiệm (Dry-run: Chỉ kiểm định schema, bỏ qua bước ghi dữ liệu)
python -m src.pipeline.cli run --source crm --date 2026-08-29 --dry-run

# 3. Thực thi chính thức một nguồn dữ liệu theo ngày
python -m src.pipeline.cli run --source crm --date 2026-08-29

# 4. Thực thi tất cả các nguồn dữ liệu cho một ngày batch
python -m src.pipeline.cli run --all --date 2026-08-29

# 5. Xây dựng các Data Marts tầng Gold
python -m src.pipeline.gold
```

---

## 4. Cấu Trúc File Cấu Hình Nguồn (YAML Schema)

Mỗi nguồn dữ liệu tương ứng một tệp cấu hình tại `src/data_source/sources/<name>.yaml`:

```yaml
source:
  name: crm
  type: csv                      # Loại nguồn: csv | parquet | api | kafka
  connection:
    path: data/raw/crm/
    encoding: utf-8
    delimiter: ","
  schedule: daily                # Tần suất: daily | hourly | event

contract:
  ref: contracts/crm.contract.json
  version: "1.0.0"

bronze:
  destination: s3://vinfast-bronze/crm/
  mode: overwrite_partition
  add_metadata: true             # Tự động thêm: _ingested_at, _source, _batch_id, _entity

entities:
  - name: customer
    canonical_entity: customer
    identity:
      source_keys: [phone]
      canonical_key: customer_id
      strategy: match_or_create  # Chiến lược: match_or_create | match_required | match_or_null
      match_tolerance: normalize_phone
    mapping:
      - { source: phone_number, canonical: phone, transform: normalize_phone }
      - { source: full_name,     canonical: name }
      - { source: city,          canonical: city_code }
    dedup:
      keys: [phone]
      order_by: registered_at

silver:
  destination: s3://vinfast-silver/crm/
  engine: pandas                # Công cụ xử lý: pandas | spark
  partition: [year, month]
  format: parquet

plugin:                          # Plugin mở rộng (tùy chọn)
  module: src.pipeline.plugins.crm_plugin
  hooks: [pre_map, post_resolve]
```

---

## 5. Chiến Lược Giải Quyết Định Danh (Identity Resolution)

Tệp [identity_store.py](file:///d:/Project/Data_Engineering/Vinfast_v1/src/pipeline/identity_store.py) quản lý CSDL SQLite tại `data/mapping/identity.db` với bảng `identity_mapping(entity, canonical_id, key_name, key_value, source)` và chỉ mục trên `(entity, key_name, key_value)`.

Mã **Canonical ID** được tạo định đề từ chuỗi băm SHA256 8 ký tự với tiền tố thực thể: `CUS-a3f2b1c9`, `VFS-f0ec062e`, `DLR-x1y2z3w4`. Khi chạy lại cùng dữ liệu đầu vào, hệ thống tạo ra đúng mã ID cũ (đảm bảo tính định đề).

| Chiến lược (Strategy) | Khi tìm thấy mã sẵn có | Khi không tìm thấy | Ứng dụng thực tế |
| :--- | :--- | :--- | :--- |
| `match_or_create` | Giữ mã ID sẵn có. | **Tạo mới mã ID** và ghi bản ghi ánh xạ. | Thực thể Master Data: Khách hàng (customer), Đại lý (dealer). |
| `match_required` | Giữ mã ID sẵn có. | **Từ chối (Reject)** bản ghi và chuyển vào `data/rejected/`. | Thực thể có khóa ngoại bắt buộc: Đơn hàng (sales_order), Tương tác (interaction). |
| `match_or_null` | Giữ mã ID sẵn có. | Gán giá trị `NULL` (vẫn giữ bản ghi trong luồng). | Phiên sạc ngoài đối tác (khách sạc vãng lai không có mã VIN). |

* **Trường hợp Passthrough:** Khi `canonical_key` trùng với khóa nguồn (ví dụ: `vehicle_id` trong dữ liệu Telemetry), giá trị nguồn được sử dụng trực tiếp làm `canonical_id` mà không qua bước băm SHA256.

---

## 6. Hệ Thống Plugin Mở Rộng

* **80% Cấu hình YAML:** Xử lý các tác vụ đổi tên trường, chuẩn hóa số điện thoại, tính toán biểu thức điều kiện và khử trùng lặp.
* **20% Plugin Code:** Phục vụ các tác vụ phức tạp như bổ sung dữ liệu liên bảng hoặc tính toán chỉ số riêng biệt. Các Plugin kế thừa lớp `SourcePlugin` từ [plugins/base.py](file:///d:/Project/Data_Engineering/Vinfast_v1/src/pipeline/plugins/base.py) với 3 hàm hook:
  * `pre_map`: Xử lý dữ liệu thô trước bước đổi tên trường.
  * `post_resolve`: Xử lý dữ liệu sau khi hoàn tất giải quyết định danh.
  * `pre_conform`: Xử lý biến đổi cuối cùng trước khi ghi vào Silver.

---

## 7. Cấu Trúc Thư Mục Lưu Trữ Đã Tạo (Artifacts)

| Đường dẫn lưu trữ | Mô tả nội dung dữ liệu |
| :--- | :--- |
| `data/bronze/<source>/<date>/` | Thư mục lưu trữ tập tin Parquet tầng Bronze cục bộ (khi không kết nối MinIO). |
| `data/silver/<source>/<entity>/year=/month=/day=/` | Thư mục lưu trữ tập tin Parquet tầng Silver phân vùng Hive cục bộ. |
| `data/quality_reports/<source>_<entity>_<date>.json` | Báo cáo kiểm định chất lượng dữ liệu chi tiết theo từng đợt xử lý. |
| `data/rejected/<source>_<entity>_<date>.parquet` | Tập tin lưu các bản ghi bị loại bỏ do không thỏa mãn chiến lược `match_required`. |
| `data/mapping/identity.db` | Cơ sở dữ liệu SQLite lưu trữ bảng ánh xạ định danh thực thể. |
| `data/gold/mart_*.parquet` | Tập tin lưu trữ các Data Marts tầng Gold (`mart_customer_360`, `mart_sales_pipeline`, `mart_charging_revenue`). |
