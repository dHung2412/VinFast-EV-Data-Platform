from __future__ import annotations

import json
import pathlib
from typing import Any, Callable

import pandas as pd
import yaml

# Thư mục chứa tệp cấu hình YAML và Hợp đồng dữ liệu JSON
SOURCES_DIR = pathlib.Path("src/data_source/sources")
CONTRACTS_DIR = pathlib.Path("src/data_source/contracts")

# Các giá trị hợp lệ theo quy chuẩn cấu hình
VALID_SOURCE_TYPES = {"csv", "api", "parquet", "kafka"}
VALID_IDENTITY_STRATEGIES = {"match_or_create", "match_required", "match_or_null"}
VALID_TRANSFORMS = {"none", "normalize_phone", "parse_date", "lower", "upper"}
VALID_ENGINES = {"pandas", "spark"}


def normalize_phone(phone: str | None) -> str | None:
    """Chuẩn hóa số điện thoại về định dạng tiêu chuẩn Việt Nam (0901234567)."""
    if phone is None:
        return None

    s = str(phone).strip().replace(" ", "").replace("-", "")
    if s.startswith("+84"):
        s = "0" + s[3:]
    elif s.startswith("84") and len(s) == 11:
        s = "0" + s[2:]

    return s


# Registry đăng ký các hàm biến đổi trường dữ liệu
TRANSFORM_REGISTRY: dict[str, Callable[[Any], Any]] = {
    "normalize_phone": normalize_phone,
    "parse_date": lambda v: pd.to_datetime(v) if v is not None and str(v).strip() != "" else v,
    "lower": lambda v: str(v).lower() if v is not None else v,
    "upper": lambda v: str(v).upper() if v is not None else v,
    "none": lambda v: v,
}


def load_config(source_name: str, sources_dir: pathlib.Path | None = None) -> dict[str, Any]:
    """Nạp tệp cấu hình nguồn YAML từ thư mục sources."""
    base_dirs = [sources_dir] if sources_dir else [SOURCES_DIR, pathlib.Path("sources")]

    path = None
    for base in base_dirs:
        candidate = base / f"{source_name}.yaml"
        if candidate.exists():
            path = candidate
            break

    if path is None:
        raise FileNotFoundError(f"Không tìm thấy cấu hình nguồn: {source_name}.yaml")

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    validate_config(config, source_name)
    return config


def load_contract(contract_ref: str, contracts_dir: pathlib.Path | None = None) -> dict[str, Any]:
    """Nạp tệp Hợp đồng dữ liệu JSON (Data Contract)."""
    ref_path = pathlib.Path(contract_ref)

    candidates = [
        ref_path,
        CONTRACTS_DIR / ref_path.name,
        pathlib.Path("contracts") / ref_path.name,
        pathlib.Path(contract_ref.replace("contracts/", "")),
    ]
    if contracts_dir:
        candidates.insert(0, contracts_dir / ref_path.name)

    for candidate in candidates:
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))

    raise FileNotFoundError(f"Không tìm thấy tệp Hợp đồng dữ liệu JSON: {contract_ref}")


def validate_config(config: dict[str, Any], source_name: str) -> None:
    """Kiểm tra tính hợp lệ của cấu hình nguồn YAML."""
    errors: list[str] = []

    if "source" not in config:
        errors.append("Thiếu phần 'source'")
    else:
        stype = config["source"].get("type", "")
        if stype not in VALID_SOURCE_TYPES:
            errors.append(f"Invalid source.type: {stype!r} (kỳ vọng một trong {VALID_SOURCE_TYPES})")

        if "schedule" in config["source"] and config["source"]["schedule"] not in {"daily", "hourly", "event"}:
            errors.append(f"Invalid source.schedule: {config['source']['schedule']!r}")

    if "contract" not in config:
        errors.append("Thiếu phần 'contract'")
    elif "ref" not in config["contract"]:
        errors.append("Thiếu 'contract.ref'")

    if "bronze" not in config:
        errors.append("Thiếu phần 'bronze'")
    elif "destination" not in config["bronze"]:
        errors.append("Thiếu 'bronze.destination'")

    if "silver" not in config:
        errors.append("Thiếu phần 'silver'")
    else:
        if "destination" not in config["silver"]:
            errors.append("Thiếu 'silver.destination'")
        engine = config["silver"].get("engine", "pandas")
        if engine not in VALID_ENGINES:
            errors.append(f"Invalid silver.engine: {engine!r} (kỳ vọng {VALID_ENGINES})")

    if "entities" not in config or not config["entities"]:
        errors.append("Thiếu hoặc rỗng phần 'entities'")
    else:
        for entity in config["entities"]:
            if "name" not in entity:
                errors.append(f"Thực thể thiếu 'name': {entity}")
            if "canonical_entity" not in entity:
                errors.append(f"Thực thể {entity.get('name', '?')} thiếu 'canonical_entity'")

            if "mapping" in entity:
                for m in entity["mapping"]:
                    if "source" not in m or "canonical" not in m:
                        errors.append(f"Thực thể {entity.get('name', '?')} mapping thiếu source/canonical: {m}")
                    if "transform" in m and m["transform"] not in VALID_TRANSFORMS:
                        errors.append(f"Transform không hợp lệ: {m['transform']!r} (kỳ vọng {VALID_TRANSFORMS})")

            if "identity" in entity:
                ident = entity["identity"]
                strategy = ident.get("strategy", "")
                if strategy and strategy not in VALID_IDENTITY_STRATEGIES:
                    errors.append(f"Thực thể {entity.get('name', '?')} chiến lược định danh không hợp lệ: {strategy!r}")

    if errors:
        raise ValueError(f"Lỗi kiểm định cấu hình YAML cho nguồn {source_name}:\n" + "\n".join(f"  - {e}" for e in errors))


def list_sources(sources_dir: pathlib.Path | None = None) -> list[dict[str, Any]]:
    """Quét và liệt kê danh sách tất cả các nguồn dữ liệu từ các tệp *.yaml."""
    base_dirs = [sources_dir] if sources_dir else [SOURCES_DIR, pathlib.Path("sources")]

    base = next((d for d in base_dirs if d.exists()), SOURCES_DIR)
    if not base.exists():
        return []

    result: list[dict[str, Any]] = []
    for path in sorted(base.glob("*.yaml")):
        try:
            config = yaml.safe_load(path.read_text(encoding="utf-8"))
            result.append(
                {
                    "name": path.stem,
                    "type": config.get("source", {}).get("type", "?"),
                    "schedule": config.get("source", {}).get("schedule", "?"),
                    "contract": config.get("contract", {}).get("ref", "?"),
                    "entities": [e.get("name", "?") for e in config.get("entities", [])],
                    "valid": True,
                }
            )
        except Exception as e:
            result.append(
                {
                    "name": path.stem,
                    "type": "?",
                    "schedule": "?",
                    "contract": "?",
                    "entities": [],
                    "valid": False,
                    "error": str(e),
                }
            )

    return result


def get_available_source_names(sources_dir: pathlib.Path | None = None) -> list[str]:
    """Trả về danh sách tên tất cả các nguồn dữ liệu khả dụng."""
    sources = list_sources(sources_dir)
    return [s["name"] for s in sources if s["valid"]]
