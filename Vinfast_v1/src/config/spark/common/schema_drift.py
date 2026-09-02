from pyspark.sql import DataFrame
from pyspark.sql.types import StructType

def check_schema_drift(df: DataFrame, expected: StructType, dataset: str) -> None:
    actual_fields = {f.name: f.dataType for f in df.schema.fields}
    expected_fields = {f.name: f.dataType for f in expected.fields}

    # missing columns -> hard fail
    missing = set(expected_fields.keys()) - set(actual_fields.keys())
    if missing:
        raise ValueError(f"[{dataset}] Missing columns: {sorted(missing)} — FAIL HARD (schema drift)")

    # type mismatch -> hard fail
    for name, exp_type in expected_fields.items():
        if name not in actual_fields:
            continue
        act_type = actual_fields[name]
        # Allow DoubleType <-> LongType coercion? No, strict except nullable
        # Compare simple string representation
        if type(act_type) != type(exp_type):
            # Special allowance: IntegerType vs LongType, and Float vs Double
            act_s = act_type.simpleString()
            exp_s = exp_type.simpleString()
            # Normalize: int -> bigint, float -> double
            allow = {
                ("int", "bigint"),
                ("bigint", "int"),
                ("float", "double"),
                ("double", "float"),
            }
            if (act_s, exp_s) in allow:
                continue
            raise TypeError(
                f"[{dataset}] Type mismatch for column '{name}': expected {exp_s}, got {act_s} — FAIL HARD"
            )

    # unexpected columns -> warning only
    extra = set(actual_fields.keys()) - set(expected_fields.keys())
    # ignore hive partition columns and internal
    extra = {c for c in extra if c not in ("year", "month", "day") and not c.startswith("_")}
    if extra:
        print(f"[{dataset}] WARNING: Unexpected columns: {sorted(extra)} — not failing")
