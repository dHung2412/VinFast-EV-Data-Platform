from __future__ import annotations

from typing import Any

import pandas as pd

from src.pipeline.identity_store import IdentityMappingStore, generate_canonical_id


def resolve_identity(
    df: pd.DataFrame,
    identity_config: dict[str, Any],
    mapping_store: IdentityMappingStore,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Giải quyết và ánh xạ định danh thực thể (Identity Resolution).

    Các chiến lược hỗ trợ:
    - match_or_create: Tra cứu khóa hiện có, nếu chưa có thì tạo mới mã canonical_id định đề.
    - match_required: Bắt buộc phải khớp khóa hiện có, loại bỏ các dòng không khớp vào tập rejected.
    - match_or_null: Tra cứu khóa, giữ giá trị Null nếu không khớp.
    """
    strategy: str = identity_config.get("strategy", "match_or_null")
    source_keys: list[str] = identity_config.get("source_keys", [])
    canonical_key: str = identity_config.get("canonical_key", "canonical_id")
    canonical_entity: str = identity_config.get(
        "canonical_entity", identity_config.get("canonical_key", "unknown")
    )

    if not source_keys or df.empty:
        df[canonical_key] = None
        return df, pd.DataFrame()

    # Sao lưu các giá trị khóa nguồn ban đầu trước khi ghi đè cột canonical_key
    original_keys_df = df[source_keys].copy() if all(k in df.columns for k in source_keys) else None

    resolved_ids: list[str | None] = []

    # Tra cứu từng dòng dữ liệu trong kho ánh xạ
    for _, row in df.iterrows():
        keys_dict: dict[str, Any] = {k: row[k] for k in source_keys if k in row.index}
        found = None
        for k, v in keys_dict.items():
            if v is None or str(v).strip() in ("", "nan"):
                continue
            found = mapping_store.lookup(canonical_entity, {k: v})
            if found is not None:
                break
        resolved_ids.append(found)

    df = df.copy()
    df[canonical_key] = resolved_ids
    rejected = pd.DataFrame()

    # Trường hợp Passthrough: canonical_key chính là một khóa nguồn (ví dụ: vehicle_id trong telemetry)
    is_passthrough = canonical_key in source_keys

    if strategy == "match_or_create":
        unmatched = df[canonical_key].isna()
        for idx in df[unmatched].index:
            if original_keys_df is not None:
                keys_dict = {
                    k: original_keys_df.at[idx, k]
                    for k in source_keys
                    if k in original_keys_df.columns
                }
            else:
                keys_dict = {k: df.at[idx, k] for k in source_keys if k in df.columns}

            # Bỏ qua dòng có tất cả các khóa nguồn bị Null
            if all(v is None or str(v).strip() in ("", "nan") for v in keys_dict.values()):
                continue

            if is_passthrough:
                new_id = str(list(keys_dict.values())[0])
            else:
                new_id = generate_canonical_id(canonical_entity, keys_dict)

            df.at[idx, canonical_key] = new_id
            mapping_store.insert(
                canonical_entity,
                new_id,
                keys_dict,
                source=identity_config.get("_source", "unknown"),
            )

    elif strategy == "match_required":
        unmatched = df[canonical_key].isna()
        rejected = df[unmatched].copy()
        df = df[~unmatched].copy()

    return df, rejected
