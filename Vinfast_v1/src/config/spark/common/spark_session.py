import os
os.environ.pop("SPARK_HOME", None)  # use pyspark bundled JARs, avoid version mismatch with local Spark 3.3.4

from pyspark.sql import SparkSession

def get_spark(app_name: str = "vinfast_silver") -> SparkSession:
    endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9100")
    return (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.sql.parquet.outputTimestampType", "TIMESTAMP_MICROS")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.hadoop.fs.s3a.endpoint", endpoint)
        .config("spark.hadoop.fs.s3a.access.key", "vinfast")
        .config("spark.hadoop.fs.s3a.secret.key", "vinfast123")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.367")
        .getOrCreate()
    )
