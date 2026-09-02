# contracts/ — Hợp đồng dữ liệu (Data Contracts)

Mỗi nguồn = 1 file JSON khai báo **schema mong đợi** trước khi dữ liệu được chấp nhận vào pipeline.

## Vai trò

| Câu hỏi | Trả lời |
|---|---|
| Dữ liệu hợp lệ không? | ✅ contracts (bước **Validate**) |
| Dữ liệu xử lý thế nào? | ❌ → xem `sources/*.yaml` (bước Map/Resolve/Conform) |

Contract = "phiên kiểm định chất lượng đầu vào" — vi phạm = reject hoặc cảnh báo, không cho lỗi lọt xuống Silver/Gold.

## Files

| File | Nguồn | Tables |
|---|---|---|
| `crm.contract.json` | CRM | `customer`, `interaction` |
| `dms.contract.json` | DMS | `sales_order`, `dealer`, `inventory` |
| `charging.contract.json` | Charging external (OCPP) | `charging_session` |
| `telemetry.contract.json` | Telemetry retrofit | `telemetry_event` |
| `charging_sessions.contract.json` | Telemetry-extracted | `charging_session` |
| `entities.contract.json` | Fleet/users/stations | `users`, `vehicles`, `stations` |

## Cấu trúc 1 contract

```json
{
  "dataset": "crm",
  "version": "1.0.0",
  "tables": {
    "customer": {
      "grain": "1 row = 1 khach hang",
      "primary_keys": ["customer_code"],
      "fields": [
        {"name": "phone_number", "type": "string", "required": true,
         "pattern": "^[0-9+ ]{10,15}$"},
        {"name": "customer_status", "type": "string", "required": true,
         "enum": ["active", "inactive", "lead", "churned"]},
        {"name": "email", "type": "string", "required": false, "nullable": true}
      ]
    }
  },
  "quality_assertions": [
    {"rule": "phone_number not null", "columns": ["phone_number"]},
    {"rule": "interaction_date not in future", "columns": ["interaction_date"]}
  ]
}
```

## 4 lớp kiểm định (validator.py)

1. **Schema** — field bắt buộc có mặt, type đúng
2. **PK** — `primary_keys` không null, không trùng
3. **Constraint** — `pattern` (regex), `enum` (giá trị cho phép), `nullable`
4. **Quality assertions** — rule nghiệp vụ (`not null`, `not in future`)

## Quy ước

- Sửa schema nguồn → bump `version` (major: breaking, minor: thêm field)
- `grain` luôn khai báo — định nghĩa "1 row = gì" để join
- Contract không biết gì về canonical model — giữ neutral so với `sources/*.yaml`
