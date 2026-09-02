from __future__ import annotations

import importlib
from typing import Any

import pandas as pd


class SourcePlugin:
    """Giao diện (Interface) cơ sở cho các Plugin mở rộng của từng nguồn dữ liệu."""

    def pre_map(self, df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
        """Thực hiện biến đổi dữ liệu trước bước Rename (xử lý logic riêng với schema thô)."""
        return df

    def post_resolve(self, df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
        """Bổ sung/xử lý dữ liệu sau khi đã giải quyết xong định danh canonical_id."""
        return df

    def pre_conform(self, df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
        """Thực hiện biến đổi cuối cùng trước khi ghi tập dữ liệu Silver."""
        return df


def load_plugin(plugin_config: dict[str, Any] | None) -> SourcePlugin | None:
    """Tải động (Dynamic Load) Plugin từ cấu hình YAML dựa trên đường dẫn module."""
    if not plugin_config or "module" not in plugin_config:
        return None

    try:
        module = importlib.import_module(plugin_config["module"])
        cls_name = next(
            (name for name in dir(module) if name.endswith("Plugin") and name != "SourcePlugin"),
            None,
        )
        if cls_name is None:
            return None

        cls = getattr(module, cls_name)
        return cls()
    except (ImportError, AttributeError):
        return None
