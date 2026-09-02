from __future__ import annotations

import json
import pathlib

import pandas as pd

from src.pipeline.config_loader import load_config, load_contract
from src.pipeline.conformer import conform_pandas, conform_spark
from src.pipeline.extractor import extract
from src.pipeline.identity_store import IdentityMappingStore
from src.pipeline.lander import land
from src.pipeline.mapper import map_fields
from src.pipeline.plugins.base import load_plugin
from src.pipeline.resolver import resolve_identity
from src.pipeline.validator import validate

DEFAULT_DB_PATH = "data/mapping/identity.db"


def run_source(
    source_name: str,
    batch_date: str,
    dry_run: bool = False,
) -> None:
    """Điều phối 6 bước trong quy trình xử lý dữ liệu tự động cho một nguồn:

    1. Extract   : Trích xuất dữ liệu thô (CSV / Parquet).
    2. Validate  : Kiểm định chất lượng theo Data Contract.
    3. Land      : Lưu trữ tầng Bronze (MinIO / Local).
    4. Map       : Đổi tên cột và chuyển đổi kiểu dữ liệu.
    5. Resolve   : Giải quyết và ánh xạ định danh thực thể.
    6. Conform   : Tính toán phái sinh & lưu trữ tầng Silver.
    """
    config = load_config(source_name)
    contract = load_contract(config["contract"]["ref"])
    plugin = load_plugin(config.get("plugin"))

    # Kết nối kho lưu trữ ánh xạ định danh
    mapping_store = IdentityMappingStore(DEFAULT_DB_PATH)
    is_multi = len(config["entities"]) > 1

    for entity in config["entities"]:
        entity_name: str = entity.get("name", "unknown")
        entity["_is_multi"] = is_multi
        print(f"\n[{source_name}/{entity_name}] Batch: {batch_date}")

        if "identity" in entity:
            entity["identity"]["_source"] = source_name
            if "canonical_entity" not in entity["identity"]:
                entity["identity"]["canonical_entity"] = entity.get("canonical_entity", entity_name)

        # Bước 1: Extract (Trích xuất)
        print(f"  [extract] type={config['source'].get('type')} -> {config['source'].get('connection', {})}")
        try:
            df = _extract_for_entity(config["source"], entity, batch_date=batch_date)
        except FileNotFoundError as e:
            if dry_run:
                print(f"  [extract] Không tìm thấy dữ liệu (Bỏ qua cho chế độ dry-run): {e}")
                mapping_store.commit()
                continue
            raise

        if df.empty:
            print(f"  [{entity_name}] Dữ liệu rỗng, bỏ qua xử lý")
            continue

        # Plugin Hook: pre_map
        if plugin and "pre_map" in config.get("plugin", {}).get("hooks", []):
            df = plugin.pre_map(df, config)

        # Bước 2: Validate (Kiểm định chất lượng)
        report = validate(df, contract, entity_name)
        print(f"  [validate] {report.summary()}")
        if not dry_run:
            _save_report(report, source_name, entity_name, batch_date)

        # Bước 3: Land (Lưu trữ tầng Bronze)
        land(df, config["bronze"], source_name, batch_date, dry_run=dry_run, entity_name=entity_name)

        if dry_run:
            print("  [dry-run] Chế độ chạy thử: Bỏ qua các bước Map -> Resolve -> Conform")
            mapping_store.commit()
            continue

        # Bước 4: Map (Biến đổi & Đổi tên trường)
        mapped = map_fields(df, entity)

        # Bước 5: Resolve (Giải quyết định danh)
        if "identity" in entity:
            mapped, rejected = resolve_identity(mapped, entity["identity"], mapping_store)
            mapping_store.commit()

            if not rejected.empty:
                _save_rejected(rejected, source_name, entity_name, batch_date)
                print(f"  [resolver] Từ chối {len(rejected)} dòng (strategy={entity['identity'].get('strategy')})")

            print(f"  [resolver] Giải quyết {len(mapped)} dòng -> canonical_key={entity['identity'].get('canonical_key')}")
        else:
            mapping_store.commit()

        # Plugin Hooks: post_resolve / pre_conform
        if plugin:
            hooks = config.get("plugin", {}).get("hooks", [])
            if "post_resolve" in hooks:
                mapped = plugin.post_resolve(mapped, config)
            if "pre_conform" in hooks:
                mapped = plugin.pre_conform(mapped, config)

        # Bước 6: Conform (Lưu trữ tầng Silver)
        silver_cfg = config["silver"]
        engine = silver_cfg.get("engine", "pandas")

        if engine == "spark":
            from src.spark_jobs.common.spark_session import get_spark

            spark = get_spark(f"pipeline_{source_name}")
            conform_spark(mapped, silver_cfg, entity, spark, batch_date=batch_date)
            spark.stop()
        else:
            conform_pandas(mapped, silver_cfg, entity, batch_date=batch_date)

    mapping_store.close()
    print(f"\n[{source_name}] Hoàn tất batch={batch_date}.\n")


def _extract_for_entity(
    source_config: dict, entity: dict, batch_date: str | None = None
) -> pd.DataFrame:
    """Điều hướng trích xuất dữ liệu theo từng thực thể cụ thể."""
    stype = source_config.get("type", "")

    if stype == "csv":
        path = pathlib.Path(source_config.get("connection", {}).get("path", ""))
        entity_name: str = entity.get("name", "")
        candidate = path / f"{entity_name}.csv" if entity_name else path
        if candidate.is_file():
            return pd.read_csv(
                candidate, encoding=source_config["connection"].get("encoding", "utf-8")
            )
        return extract(source_config, date=batch_date)

    if stype == "parquet":
        # Ưu tiên tệp phẳng theo thực thể (snapshot dimension): {path}/{entity}.parquet
        path = pathlib.Path(source_config.get("connection", {}).get("path", ""))
        entity_name = entity.get("name", "")
        flat = path / f"{entity_name}.parquet" if entity_name else None
        if flat and flat.is_file():
            return pd.read_parquet(flat, engine="pyarrow")

    return extract(source_config, date=batch_date)


def _save_report(report: Any, source_name: str, entity_name: str, batch_date: str) -> None:
    """Lưu báo cáo kết quả kiểm định chất lượng dữ liệu dạng JSON."""
    out_dir = pathlib.Path("data/quality_reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{source_name}_{entity_name}_{batch_date}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8")


def _save_rejected(
    rejected_df: pd.DataFrame, source_name: str, entity_name: str, batch_date: str
) -> None:
    """Lưu các bản ghi không khớp quy tắc định danh vào thư mục data/rejected."""
    out_dir = pathlib.Path("data/rejected")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{source_name}_{entity_name}_{batch_date}.parquet"
    rejected_df.to_parquet(path, coerce_timestamps="us", compression="snappy")
