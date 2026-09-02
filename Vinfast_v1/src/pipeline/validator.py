from __future__ import annotations

from typing import Any
import pandas as pd


class ValidationResult:
    """Kết quả chi tiết của từng phép kiểm định dữ liệu (Check Result)."""

    def __init__(
        self,
        check_name: str,
        passed: bool,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.check_name = check_name
        self.passed = passed
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
        }


class ValidationReport:
    """Báo cáo tổng hợp kết quả kiểm định chất lượng dữ liệu theo Hợp đồng dữ liệu."""

    def __init__(
        self,
        dataset_name: str,
        total_rows: int,
        results: list[ValidationResult],
    ) -> None:
        self.dataset_name = dataset_name
        self.total_rows = total_rows
        self.results = results

    @property
    def is_valid(self) -> bool:
        return all(r.passed for r in self.results)

    def summary(self) -> str:
        passed_cnt = sum(1 for r in self.results if r.passed)
        total_cnt = len(self.results)
        status = "PASSED" if self.is_valid else "FAILED"
        return (
            f"{status} ({passed_cnt}/{total_cnt} checks passed) - "
            f"Rows: {self.total_rows} - Dataset: {self.dataset_name}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "total_rows": self.total_rows,
            "is_valid": self.is_valid,
            "results": [r.to_dict() for r in self.results],
        }


class DataValidator:
    """Bộ kiểm định chất lượng dữ liệu dựa trên quy tắc Data Contract."""

    def run_all(
        self,
        df: pd.DataFrame,
        contract: dict[str, Any],
        aux: dict[str, Any] | None = None,
    ) -> ValidationReport:
        dataset_name = contract.get("dataset", "unknown")
        total_rows = len(df)
        results: list[ValidationResult] = []

        # 1. Kiểm tra sự tồn tại và tính không Null của các cột
        fields = contract.get("fields", [])
        for field in fields:
            fname = field.get("name")
            if not fname:
                continue

            if fname not in df.columns:
                results.append(
                    ValidationResult(
                        check_name=f"field_exists_{fname}",
                        passed=False,
                        message=f"Cột '{fname}' không tồn tại trong DataFrame.",
                    )
                )
            else:
                nullable = field.get("nullable", True)
                if not nullable:
                    null_cnt = int(df[fname].isna().sum())
                    passed = null_cnt == 0
                    results.append(
                        ValidationResult(
                            check_name=f"field_not_null_{fname}",
                            passed=passed,
                            message=(
                                f"Cột '{fname}' có {null_cnt} giá trị Null (không cho phép Null)."
                                if not passed
                                else f"Cột '{fname}' đảm bảo không có giá trị Null."
                            ),
                            details={"null_count": null_cnt},
                        )
                    )

        # 2. Kiểm tra tính duy nhất của Khóa chính (Primary Key Uniqueness)
        pk_cols = contract.get("primary_keys", [])
        if pk_cols:
            avail_pks = [c for c in pk_cols if c in df.columns]
            if len(avail_pks) == len(pk_cols):
                dup_cnt = int(df.duplicated(subset=avail_pks).sum())
                passed = dup_cnt == 0
                results.append(
                    ValidationResult(
                        check_name="primary_key_uniqueness",
                        passed=passed,
                        message=(
                            f"Phát hiện {dup_cnt} dòng trùng lặp khóa chính {pk_cols}."
                            if not passed
                            else f"Khóa chính {pk_cols} đảm bảo tính duy nhất."
                        ),
                        details={"duplicate_count": dup_cnt, "pk_columns": pk_cols},
                    )
                )

        if not results:
            results.append(
                ValidationResult(
                    check_name="schema_check",
                    passed=True,
                    message="Cấu trúc DataFrame hợp lệ.",
                )
            )

        return ValidationReport(dataset_name=dataset_name, total_rows=total_rows, results=results)


def validate(
    df: pd.DataFrame,
    contract: dict[str, Any],
    entity_name: str | None = None,
    aux: dict[str, Any] | None = None,
) -> ValidationReport:
    """Thực thi kiểm định DataFrame theo quy chuẩn Data Contract (hỗ trợ cả đơn bảng và đa bảng)."""
    validator = DataValidator()

    # Hợp đồng đa bảng (Multi-table contract): Trích xuất định nghĩa bảng tương ứng
    if "tables" in contract and entity_name:
        tables = contract["tables"]
        if entity_name in tables:
            table_def = tables[entity_name]
            entity_contract = {
                "dataset": f"{contract.get('dataset', '?')}/{entity_name}",
                "fields": table_def.get("fields", []),
                "primary_keys": table_def.get("primary_keys", []),
                "quality_assertions": contract.get("quality_assertions", []),
            }
            return validator.run_all(df, entity_contract, aux)

    # Hợp đồng đơn bảng (Single-table contract)
    return validator.run_all(df, contract, aux)
