# sources/ — Cấu hình xử lý nguồn (Pipeline Config)

Mỗi nguồn = 1 file YAML khai báo **cách xử lý** nguồn đó. Pipeline đọc config để chạy 6 bước mà không cần code mới — metadata-driven.

## Vai trò

| File | Trả lời | Bước pipeline |
|---|---|---|
| `contracts/*.json` | Dữ liệu **hợp lệ không?** | Validate |
| `sources/*.yaml` | Dữ liệu **xử lý thế nào?** | Extract → Map → Resolve → Conform |

YAML là "hộ chiếu" của nguồn: khai báo field map về canonical entity nào, khớp danh tính bằng key nào, dedup thế nào, partition ra sao.

## Files

| File | Nguồn | Engine | Entities → Canonical |
|---|---|---|---|
| `crm.yaml` | CRM (csv) | pandas | customer, interaction |
| `dms.yaml` | DMS (csv) | pandas | sales_order, dealer, inventory |
| `charging.yaml` | Charging ext (csv) | pandas | charging_session |
| `telemetry.yaml` | Telemetry (hive parquet) | spark | telemetry_event |

## Cấu trúc 1 YAML (5 khối)

```yaml
source:                       # 1. Nguồn đọc từ đâu
  name: crm
  type: csv
  connection: { path: data/raw/crm/ }
  schedule: daily

contract:                     # 2. Validate bằng contract nào
  ref: contracts/crm.contract.json

bronze:                       # 3. Land raw vào đâu
  destination: s3://vinfast-bronze/crm/
  partition: [ingest_date]

entities:                     # 4. Xử lý từng entity (lõi của YAML)
  - name: customer
    canonical_entity: customer
    identity:
      source_keys: [phone]          # key khớp danh tính
      canonical_key: customer_id
      strategy: match_or_create     # match_or_create | match_required | match_or_null
    mapping:                        # field nguồn → canonical + transform
      - { source: phone_number, canonical: phone, transform: normalize_phone }
      - { source: customer_status, canonical: status }
    dedup: { keys: [phone], order_by: registered_at }
    quality: { reject_on_error: false, min_rows: 1 }

silver:                       # 5. Ghi Silver ở đâu, engine nào
  destination: s3://vinfast-silver/crm/
  engine: pandas                   # pandas | spark (dữ liệu lớn)
  partition: [year, month]
```

## Transform có sẵn (không cần plugin)

`normalize_phone` · `parse_date` · `lower` · `upper` · `least()` · `AND/OR/NOT` (expression)

## 3 chiến lược identity

| Strategy | Không khớp thì sao | Dùng cho |
|---|---|---|
| `match_or_create` | Tạo ID mới (deterministic SHA256 `CUS-hash8`) | customer, vehicle, dealer |
| `match_required` | Reject row | Bảng con bắt buộc cha tồn tại |
| `match_or_null` | Giữ row, ID = null | interaction, charging VIN 30% null |

## Bài toán giải quyết: N nguồn → 1 canonical model

```
CRM_X (mobile)     ──┐
CRM_Y (phone)      ──┼─ mapping → canonical field: phone ──► 1 customer_id
DMS (customer_tel) ──┘   identity: match_or_create
```

Khách hàng `0901234567` xuất hiện ở nhiều nguồn → nhận cùng 1 `CUS-xxxx`. Onboard nguồn mới: `cp` YAML → sửa mapping → thêm 1 dòng `SOURCES` trong DAG.

## Onboarding nguồn mới (5 phút)

1. Phân tích: bản ghi, PK, field nào map về canonical entity?
2. Viết `contracts/<source>.contract.json`
3. Viết `sources/<source>.yaml`
4. (20% trường hợp) Plugin `pipeline/plugins/<source>_plugin.py` — transform phức tạp
5. `python -m pipeline.cli run --source <source> --date ... --dry-run` → verify
