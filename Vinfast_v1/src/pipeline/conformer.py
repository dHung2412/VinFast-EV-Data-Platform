from __future__ import annotations

import io
import pathlib
import re
from typing import Any

import pandas as pd


def _normalize_expr(expr: str) -> str:
    """Chuẩn hóa biểu thức SQL (AND/OR/NOT) sang cú pháp eval của Pandas."""
    e = re.sub(r"\bAND\b", "and", expr, flags=re.IGNORECASE)
    e = re.sub(r"\bOR\b", "or", e, flags=re.IGNORECASE)
    e = re.sub(r"\bNOT\b", "not", e, flags=re.IGNORECASE)
    return e


def conform_pandas(
    df: pd.DataFrame,
    silver_config: dict[str, Any],
    entity_config: dict[str, Any],
    batch_date: str | None = None,
) -> pd.DataFrame | str:
    """Ghi tập dữ liệu Silver bằng Pandas cho nguồn tập tin vừa/nhỏ (lưu trữ MinIO S3 hoặc Local)."""
    # 1. Tính toán các cột phái sinh (Derived columns)
    for dc in silver_config.get("derived_columns", []):
        expr: str = dc["expr"]
        name: str = dc["name"]
        try:
            if expr.strip().startswith("'") and expr.strip().endswith("'"):
                df[name] = expr.strip()[1:-1]
            elif name in ("duration_min", "duration_hours") and "started_at" in df.columns and "ended_at" in df.columns:
                diff = (pd.to_datetime(df["ended_at"]) - pd.to_datetime(df["started_at"])).dt.total_seconds()
                df[name] = diff / 60.0 if name == "duration_min" else diff / 3600.0
            elif expr in ("duration_min_computed", "duration_hours_computed"):
                diff = (pd.to_datetime(df["ended_at"]) - pd.to_datetime(df["started_at"])).dt.total_seconds()
                df[name] = diff / 60.0 if name == "duration_min" else diff / 3600.0
            elif expr.strip().startswith("least("):
                inner = expr.strip()[6:-1]
                cols = [c.strip() for c in inner.split(",")]
                avail = [c for c in cols if c in df.columns]
                df[name] = df[avail].min(axis=1) if avail else None
            else:
                df[name] = df.eval(_normalize_expr(expr))
        except Exception as e:
            print(f"  [conformer] Cảnh báo: Tính cột phái sinh '{name}' với biểu thức '{expr}' thất bại: {e}")
            df[name] = None

    # 2. Loại bỏ trùng lặp (Dedup)
    dedup_config = entity_config.get("dedup")
    if dedup_config:
        before = len(df)
        df = df.drop_duplicates(subset=dedup_config["keys"], keep="last")
        if len(df) != before:
            print(f"  [conformer] Khử trùng lặp: {before} -> {len(df)} dòng (keys={dedup_config['keys']})")

    dest: str = silver_config.get("destination", "")
    dest_s3 = dest.startswith("s3://")
    partition_cols = silver_config.get("partition") or []

    # 3. Thêm các cột phân vùng nếu chưa có
    if partition_cols:
        for pc in partition_cols:
            if pc not in df.columns:
                if batch_date and pc in ("year", "month", "day"):
                    y, m, d = batch_date.split("-")
                    df[pc] = int(y) if pc == "year" else (int(m) if pc == "month" else int(d))
                elif batch_date and pc == "ingest_date":
                    df[pc] = batch_date
                elif pc in ("year", "month", "day") and "event_timestamp" in df.columns:
                    try:
                        ts = pd.to_datetime(df["event_timestamp"].iloc[0])
                        df[pc] = ts.year if pc == "year" else (ts.month if pc == "month" else ts.day)
                    except Exception:
                        pass
                elif pc == "ingest_date" and "_ingested_at" in df.columns:
                    df[pc] = pd.to_datetime(df["_ingested_at"].iloc[0]).strftime("%Y-%m-%d")

    entity_name = entity_config.get("name", "unknown")
    is_multi = entity_config.get("_is_multi", False)

    if dest_s3:
        dest_entity = dest.rstrip("/") + f"/{entity_name}/" if is_multi else dest
        # snapshot=true: bảng dimension hiện trạng, ghi đè khóa cố định (không phân vùng theo ngày)
        snapshot = silver_config.get("snapshot", False)
        try:
            _write_minio(df, dest_entity, partition_date=None if snapshot else batch_date)
            printed = f"{dest_entity}" + (f" partition={batch_date}" if (batch_date and not snapshot) else "")
            print(f"  [conformer: pandas] {len(df)} dòng -> {printed}")
        except Exception as e:
            # Lưu local Parquet dự phòng theo phân vùng Hive
            try:
                bucket_and_prefix = dest_entity.replace("s3://", "").rstrip("/")
                prefix = bucket_and_prefix.split("/", 1)[1] if "/" in bucket_and_prefix else bucket_and_prefix
                local_base = pathlib.Path("data/silver") / prefix
            except Exception:
                local_base = pathlib.Path("data/silver") / entity_name

            if partition_cols and all(c in df.columns for c in partition_cols):
                hive_path = local_base
                for pc in partition_cols:
                    val = df[pc].iloc[0]
                    if pc in ("month", "day"):
                        val = f"{int(val):02d}"
                    hive_path = hive_path / f"{pc}={val}"

                hive_path.mkdir(parents=True, exist_ok=True)
                df.to_parquet(hive_path / "part-0000.parquet", coerce_timestamps="us", compression="snappy")
                print(f"  [conformer: pandas] {len(df)} dòng -> {hive_path} (Local fallback: {e})")
            else:
                local_base.mkdir(parents=True, exist_ok=True)
                out_file = local_base / f"{entity_name}.parquet"
                df.to_parquet(out_file, coerce_timestamps="us", compression="snappy")
                print(f"  [conformer: pandas] {len(df)} dòng -> {out_file} (Local fallback: {e})")

        return dest_entity

    # Lưu tập tin cục bộ
    local_path = pathlib.Path(dest) if dest else pathlib.Path(f"data/silver/{entity_name}")
    local_path.mkdir(parents=True, exist_ok=True)
    out_file = local_path / f"{entity_name}.parquet"
    df.to_parquet(out_file, coerce_timestamps="us", compression="snappy")
    print(f"  [conformer: pandas] {len(df)} dòng -> {out_file}")

    return str(out_file)


def _to_s3a(path: str) -> str:
    """Chuyển đổi tiền tố s3:// sang s3a:// cho Hadoop/Spark."""
    return "s3a://" + path[5:] if path.startswith("s3://") else path


def conform_spark(
    df_pd: pd.DataFrame,
    silver_config: dict[str, Any],
    entity_config: dict[str, Any],
    spark: Any,
    batch_date: str | None = None,
) -> str:
    """Ghi tập dữ liệu Silver bằng PySpark cho khối lượng dữ liệu lớn."""
    dest: str = silver_config.get("destination", "")
    dest_s3a = _to_s3a(dest)
    partition_cols = silver_config.get("partition") or []

    if partition_cols:
        for pc in partition_cols:
            if pc not in df_pd.columns and batch_date:
                parts = batch_date.split("-")
                if pc == "year":
                    df_pd[pc] = int(parts[0])
                elif pc == "month":
                    df_pd[pc] = int(parts[1])
                elif pc == "day":
                    df_pd[pc] = int(parts[2])
                elif pc == "ingest_date":
                    df_pd[pc] = batch_date

    sdf = spark.createDataFrame(df_pd)

    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    for dc in silver_config.get("derived_columns", []):
        expr = dc["expr"]
        name = dc["name"]
        if expr.strip().startswith("'") and expr.strip().endswith("'"):
            sdf = sdf.withColumn(name, F.lit(expr.strip()[1:-1]))
        else:
            sdf = sdf.withColumn(name, F.expr(expr))

    dedup_config = entity_config.get("dedup")
    if dedup_config:
        w = Window.partitionBy(*dedup_config["keys"]).orderBy(F.col(dedup_config["order_by"]).desc())
        sdf = sdf.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn")

    try:
        if partition_cols:
            sdf.coalesce(1).write.mode("overwrite").partitionBy(*partition_cols).parquet(dest_s3a)
        else:
            sdf.coalesce(1).write.mode("overwrite").parquet(dest_s3a)

        print(f"  [conformer: spark] {len(df_pd)} dòng -> {dest}")
        return dest
    except Exception as e:
        fallback_base = pathlib.Path("data/silver") / entity_config.get(
            "canonical_entity", entity_config.get("name", "telemetry")
        )
        if batch_date and partition_cols:
            parts = batch_date.split("-")
            y, m, d = parts[0], f"{int(parts[1]):02d}", f"{int(parts[2]):02d}"
            hive_path = fallback_base

            for pc in partition_cols:
                val = y if pc == "year" else (m if pc == "month" else (d if pc == "day" else batch_date))
                hive_path = hive_path / f"{pc}={val}"

            hive_path.mkdir(parents=True, exist_ok=True)
            try:
                pdf_fallback = sdf.toPandas()
            except Exception:
                pdf_fallback = df_pd

            pdf_fallback.to_parquet(hive_path / "part-0000.parquet", coerce_timestamps="us", compression="snappy")
            print(f"  [conformer: spark] {len(df_pd)} dòng -> {hive_path} (Local fallback: {e})")
            return str(hive_path)

        fallback_base.mkdir(parents=True, exist_ok=True)
        try:
            sdf.coalesce(1).toPandas().to_parquet(fallback_base / "data.parquet", coerce_timestamps="us", compression="snappy")
        except Exception:
            df_pd.to_parquet(fallback_base / "data.parquet", coerce_timestamps="us", compression="snappy")

        print(f"  [conformer: spark] {len(df_pd)} dòng -> {fallback_base} (Local fallback: {e})")
        return str(fallback_base)


def _write_minio(df: pd.DataFrame, dest: str, partition_date: str | None = None) -> None:
    """Đẩy tệp Parquet trực tiếp vào MinIO S3 bucket."""
    import os
    import boto3
    from botocore.config import Config

    parts = dest.replace("s3://", "").split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    key_prefix = prefix.rstrip("/")
    key = f"{key_prefix}/{partition_date}/data.parquet" if partition_date else f"{key_prefix}/data.parquet"

    endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9100")
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id="vinfast",
        aws_secret_access_key="vinfast123",
        config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 0}),
    )

    buf = io.BytesIO()
    df.to_parquet(buf, coerce_timestamps="us", compression="snappy")
    buf.seek(0)
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())
