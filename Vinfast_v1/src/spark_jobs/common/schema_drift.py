from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql.types import StructType


def check_schema_drift(df: DataFrame, expected: StructType, dataset: str) -> None:
    """Kiểm tra biến động cấu hình schema (Schema Drift) giữa DataFrame thực tế và kỳ vọng."""
    actual_fields = {f.name: f.dataType for f in df.schema.fields}
    expected_fields = {f.name: f.dataType for f in expected.fields}

    # 1. Kiểm tra cột bị thiếu -> Báo lỗi hệ thống dừng xử lý (Hard fail)
    missing = set(expected_fields.keys()) - set(actual_fields.keys())
    if missing:
        raise ValueError(f"[{dataset}] Thiếu các cột bắt buộc: {sorted(missing)} — DỪNG XỬ LÝ (Schema Drift)")

    # 2. Kiểm tra không tương thích kiểu dữ liệu -> Báo lỗi kiểu (Hard fail)
    for name, exp_type in expected_fields.items():
        if name not in actual_fields:
            continue

        act_type = actual_fields[name]
        if type(act_type) != type(exp_type):
            act_s = act_type.simpleString()
            exp_s = exp_type.simpleString()

            # Cho phép ép kiểu an toàn giữa Integer/Long và Float/Double
            allow = {
                ("int", "bigint"),
                ("bigint", "int"),
                ("float", "double"),
                ("double", "float"),
            }
            if (act_s, exp_s) in allow:
                continue

            raise TypeError(
                f"[{dataset}] Sai lệch kiểu dữ liệu tại cột '{name}': Kỳ vọng {exp_s}, nhận được {act_s} — DỪNG XỬ LÝ"
            )

    # 3. Kiểm tra cột dư thừa -> Cảnh báo hệ thống (Warning)
    extra = set(actual_fields.keys()) - set(expected_fields.keys())
    extra = {c for c in extra if c not in ("year", "month", "day") and not c.startswith("_")}

    if extra:
        print(f"[{dataset}] CẢNH BÁO: Phát hiện các cột không khai báo: {sorted(extra)}")
