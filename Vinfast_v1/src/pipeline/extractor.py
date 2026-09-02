from __future__ import annotations

import pathlib
from typing import Any

import pandas as pd


def extract(source_config: dict[str, Any], date: str | None = None) -> pd.DataFrame:
    """Trích xuất dữ liệu từ nguồn theo định dạng cấu hình (hỗ trợ CSV và Parquet)."""
    stype = source_config.get("type", "")
    conn = source_config.get("connection", {})

    if stype == "csv":
        path = pathlib.Path(conn.get("path", ""))
        encoding = conn.get("encoding", "utf-8")
        delimiter = conn.get("delimiter", ",")

        # Trường hợp đường dẫn là thư mục
        if path.is_dir():
            csv_files = list(path.glob("*.csv"))
            if not csv_files and date:
                date_path = path / date
                csv_files = list(date_path.glob("*.csv"))

            if not csv_files:
                raise FileNotFoundError(f"Không tìm thấy tệp CSV nào tại thư mục: {path}")

            dfs = [pd.read_csv(f, encoding=encoding, sep=delimiter) for f in csv_files]
            return pd.concat(dfs, ignore_index=True)

        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp CSV tại đường dẫn: {path}")

        return pd.read_csv(path, encoding=encoding, sep=delimiter)

    elif stype == "parquet":
        path = pathlib.Path(conn.get("path", ""))
        if path.is_dir():
            if date:
                # Tìm phân vùng Hive: year=YYYY/month=MM/day=DD
                parts = date.split("-")
                try:
                    y, m, d = parts[0], f"{int(parts[1]):02d}", f"{int(parts[2]):02d}"
                except (ValueError, IndexError):
                    y, m, d = parts[0], parts[1], parts[2]

                candidate = path / f"year={y}" / f"month={m}" / f"day={d}"
                if candidate.exists():
                    return pd.read_parquet(candidate)

                raise FileNotFoundError(f"Không tìm thấy phân vùng Parquet ngày {date} tại: {candidate}")

            return pd.read_parquet(path, engine="pyarrow")

        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp Parquet tại đường dẫn: {path}")

        return pd.read_parquet(path, engine="pyarrow")

    elif stype == "api":
        raise NotImplementedError("Trích xuất nguồn API: Đang phát triển ở Giai đoạn 2")

    elif stype == "kafka":
        raise NotImplementedError("Trích xuất nguồn Kafka: Đang phát triển ở Giai đoạn 2")

    else:
        raise ValueError(f"Loại nguồn dữ liệu không được hỗ trợ: {stype!r}")
