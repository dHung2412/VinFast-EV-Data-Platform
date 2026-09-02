from __future__ import annotations

import pathlib
from typing import Any

import pandas as pd

from src.pipeline.plugins.base import SourcePlugin


class ChargingInternalPlugin(SourcePlugin):
    """Plugin nguồn Charging Internal (phiên sạc VinFast trích từ telemetry).

    Hook post_resolve:
    1. Bổ sung battery_kwh từ bảng dimension vehicles (MinIO Silver snapshot,
       fallback local raw entities) để tính hiệu suất sạc.
    2. Tính các cột phái sinh phức tạp không diễn đạt được bằng expression YAML:
       duration_hours, avg_power_kw, cost_per_kwh_vnd, is_fast_charge,
       charge_efficiency_pct (chép logic 1:1 từ Spark Silver job cũ).
    """

    VEHICLES_S3_KEY = "entities/vehicles/data.parquet"
    VEHICLES_LOCAL = pathlib.Path("data/raw/entities/vehicles.parquet")

    def _load_battery_kwh(self) -> pd.Series | None:
        # 1) Ưu tiên snapshot vehicles trên MinIO Silver (pipeline entities đã chạy)
        try:
            import io
            import os

            import boto3
            from botocore.config import Config

            endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9100")
            s3 = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id="vinfast",
                aws_secret_access_key="vinfast123",
                config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 0}),
            )
            obj = s3.get_object(Bucket="vinfast-silver", Key=self.VEHICLES_S3_KEY)
            vdf = pd.read_parquet(io.BytesIO(obj["Body"].read()))
            return vdf.set_index("vehicle_id")["battery_kwh"]
        except Exception:
            pass

        # 2) Fallback: tệp entities gốc do Data Generator sinh ra
        try:
            if self.VEHICLES_LOCAL.exists():
                vdf = pd.read_parquet(self.VEHICLES_LOCAL)
                return vdf.set_index("vehicle_id")["battery_kwh"]
        except Exception:
            pass
        return None

    def post_resolve(self, df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
        out = df.copy()

        # 1. Bổ sung battery_kwh theo vehicle_id
        batt = self._load_battery_kwh()
        if batt is not None:
            out["battery_kwh"] = out["vehicle_id"].map(batt)
        else:
            out["battery_kwh"] = float("nan")

        # 2. Các cột phái sinh (logic tương đương Spark Silver job)
        out["duration_hours"] = out["duration_min"] / 60.0
        out["avg_power_kw"] = (out["kwh_delivered"] / out["duration_hours"]).where(
            out["duration_hours"] > 0, other=float("nan")
        )
        out["cost_per_kwh_vnd"] = (out["cost_vnd"] / out["kwh_delivered"]).where(
            out["kwh_delivered"] > 0, other=float("nan")
        )
        out["is_fast_charge"] = out["charger_type"] == "CCS2_DC"
        out["charge_efficiency_pct"] = (
            (out["end_soc_pct"] - out["start_soc_pct"])
            / (out["kwh_delivered"] / out["battery_kwh"] * 100.0)
            * 100.0
        ).where(
            out["battery_kwh"].notna() & (out["kwh_delivered"] > 0),
            other=float("nan"),
        )
        return out
