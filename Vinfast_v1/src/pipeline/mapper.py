from __future__ import annotations

from typing import Any

import pandas as pd

from src.pipeline.config_loader import TRANSFORM_REGISTRY


def map_fields(df: pd.DataFrame, entity_config: dict[str, Any]) -> pd.DataFrame:
    """Đổi tên cột (Rename) và biến đổi dữ liệu (Transform) từ trường nguồn sang trường chuẩn theo cấu hình YAML."""
    mappings: list[dict[str, Any]] = entity_config.get("mapping", [])
    if not mappings:
        return df

    result = pd.DataFrame()

    for m in mappings:
        src: str = m["source"]
        canonical: str = m["canonical"]
        transform: str = m.get("transform", "none")

        if src not in df.columns:
            # Cột nguồn không tồn tại -> Điền giá trị None
            result[canonical] = None
        else:
            col = df[src].copy()
            fn = TRANSFORM_REGISTRY.get(transform)

            if fn and transform != "none":
                try:
                    result[canonical] = col.apply(lambda v: fn(v) if pd.notna(v) else v)
                except Exception:
                    result[canonical] = col
            else:
                result[canonical] = col

    # Bảo toàn các cột metadata nếu có
    for meta in ["_ingested_at", "_source", "_batch_id"]:
        if meta in df.columns:
            result[meta] = df[meta]

    return result
