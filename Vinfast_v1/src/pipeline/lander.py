from __future__ import annotations

import datetime
import io
import pathlib
from typing import Any

import pandas as pd


def land(
    df: pd.DataFrame,
    bronze_config: dict[str, Any],
    source_name: str,
    batch_date: str,
    dry_run: bool = False,
    entity_name: str | None = None,
) -> str | None:
    """Lưu trữ dữ liệu vào tầng Bronze (MinIO S3 hoặc lưu local parquet dự phòng)."""
    add_metadata = bronze_config.get("add_metadata", True)
    if add_metadata:
        df = df.copy()
        df["_ingested_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        df["_source"] = source_name
        df["_batch_id"] = f"{source_name}_{batch_date}"
        if entity_name:
            df["_entity"] = entity_name

    dest: str = bronze_config.get("destination", "")

    if dry_run:
        ent = f"/{entity_name}" if entity_name else ""
        print(f"  [dry-run] Sẽ ghi {len(df)} dòng tới {dest}{ent} (partition={batch_date})")
        return dest

    # Ghi dữ liệu tới MinIO (S3) hoặc Fallback local
    if dest.startswith("s3://"):
        suffix = f"_{entity_name}" if entity_name else ""
        local_path = pathlib.Path("data/bronze") / source_name / batch_date
        local_path.mkdir(parents=True, exist_ok=True)
        out_file = local_path / f"{source_name}{suffix}_{batch_date}.parquet"

        try:
            _try_write_minio(df, dest, batch_date, entity_name=entity_name)
            ent = f"/{entity_name}" if entity_name else ""
            print(f"  [lander] {len(df)} dòng -> {dest}{ent}")
        except Exception:
            # Lưu local parquet dự phòng khi MinIO không khả dụng
            df.to_parquet(out_file, coerce_timestamps="us", compression="snappy")
            print(f"  [lander] {len(df)} dòng -> {out_file} (Local fallback, MinIO offline)")

        return dest

    # Lưu đường dẫn tệp local
    local_path = pathlib.Path(dest)
    local_path.mkdir(parents=True, exist_ok=True)
    suffix = f"_{entity_name}" if entity_name else ""
    out_file = local_path / f"{source_name}{suffix}_{batch_date}.parquet"
    df.to_parquet(out_file, coerce_timestamps="us", compression="snappy")
    print(f"  [lander] {len(df)} dòng -> {out_file}")

    return str(out_file)


def _try_write_minio(
    df: pd.DataFrame,
    dest: str,
    batch_date: str,
    entity_name: str | None = None,
) -> None:
    """Thực hiện đẩy tệp Parquet vào MinIO (S3 Bucket)."""
    import os
    import boto3
    from botocore.config import Config

    parts = dest.replace("s3://", "").split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""

    endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9100")
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id="vinfast",
        aws_secret_access_key="vinfast123",
        config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 0}),
    )

    ent = f"_{entity_name}" if entity_name else ""
    key = f"{prefix.rstrip('/')}/{batch_date}/{batch_date}{ent}.parquet"

    buf = io.BytesIO()
    df.to_parquet(buf, coerce_timestamps="us", compression="snappy")
    buf.seek(0)
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())
