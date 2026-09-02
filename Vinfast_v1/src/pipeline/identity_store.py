from __future__ import annotations

import hashlib
import pathlib
import sqlite3
from typing import Any

# Ánh xạ tiền tố (Prefix) mã ID theo từng loại thực thể chuẩn
ENTITY_PREFIX: dict[str, str] = {
    "customer": "CUS",
    "vehicle": "VFS",
    "dealer": "DLR",
    "station": "STN",
    "location": "LOC",
    "sales_order": "ORD",
    "charging_session": "CHG",
    "telemetry_event": "TLM",
    "customer_interaction": "INT",
}

# Cấu trúc bảng và chỉ mục SQLite lưu trữ định danh
SCHEMA = """
CREATE TABLE IF NOT EXISTS identity_mapping (
    entity       TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    key_name     TEXT NOT NULL,
    key_value    TEXT NOT NULL,
    source       TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (entity, key_name, key_value)
);
CREATE INDEX IF NOT EXISTS idx_identity_lookup
    ON identity_mapping(entity, key_name, key_value);
CREATE INDEX IF NOT EXISTS idx_canonical_id
    ON identity_mapping(canonical_id);
"""

DEFAULT_DB_PATH = pathlib.Path("data/mapping/identity.db")


def generate_canonical_id(canonical_entity: str, source_keys: dict[str, Any]) -> str:
    """Sinh mã định danh chuẩn (Canonical ID) định đề bằng cách băm SHA256 từ danh sách các khóa nguồn."""
    raw = "|".join(f"{k}={v}" for k, v in sorted(source_keys.items()))
    h = hashlib.sha256(raw.encode()).hexdigest()[:8]
    prefix = ENTITY_PREFIX.get(canonical_entity, "ID")
    return f"{prefix}-{h}"


class IdentityMappingStore:
    """Kho lưu trữ ánh xạ định danh thực thể (Identity Mapping Store) dựa trên cơ sở dữ liệu SQLite."""

    def __init__(self, db_path: str | pathlib.Path | None = None) -> None:
        path = pathlib.Path(db_path) if db_path else DEFAULT_DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(path)
        self.conn = sqlite3.connect(self.db_path, isolation_level=None)
        self.conn.executescript(SCHEMA)

    def lookup(self, entity: str, keys: dict[str, Any]) -> str | None:
        """Tra cứu mã canonical_id theo các khóa nguồn. Trả về None nếu không tìm thấy."""
        for key_name, key_value in keys.items():
            if key_value is None or str(key_value).strip() in ("", "nan"):
                continue

            row = self.conn.execute(
                "SELECT canonical_id FROM identity_mapping "
                "WHERE entity=? AND key_name=? AND key_value=?",
                (entity, key_name, str(key_value)),
            ).fetchone()

            if row:
                return row[0]

        return None

    def insert(
        self,
        entity: str,
        canonical_id: str,
        keys: dict[str, Any],
        source: str = "unknown",
    ) -> None:
        """Thêm mới ánh xạ định danh. Đảm bảo tính định đề (Idempotent - không trùng lặp)."""
        for key_name, key_value in keys.items():
            if key_value is None or str(key_value).strip() in ("", "nan"):
                continue

            self.conn.execute(
                "INSERT OR IGNORE INTO identity_mapping "
                "(entity, canonical_id, key_name, key_value, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (entity, canonical_id, key_name, str(key_value), source),
            )

    def commit(self) -> None:
        """Xác nhận giao dịch (Explicit commit)."""
        self.conn.commit()

    def close(self) -> None:
        """Đóng kết nối CSDL SQLite."""
        self.conn.close()

    def count(self, entity: str | None = None) -> int:
        """Đếm tổng số lượng bản ghi ánh xạ định danh trong kho."""
        if entity:
            return self.conn.execute(
                "SELECT count(*) FROM identity_mapping WHERE entity=?", (entity,)
            ).fetchone()[0]
        return self.conn.execute("SELECT count(*) FROM identity_mapping").fetchone()[0]

    def sync_from_minio(self, bucket: str = "vinfast-silver") -> int:
        """Đồng bộ bảng ánh xạ từ MinIO Parquet sang SQLite (Dự phòng cho Giai đoạn 2)."""
        return 0

    def __enter__(self) -> IdentityMappingStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
