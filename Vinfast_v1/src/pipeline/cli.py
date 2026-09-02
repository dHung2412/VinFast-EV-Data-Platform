from __future__ import annotations

import argparse
import sys
import traceback

from src.pipeline.config_loader import get_available_source_names, list_sources
from src.pipeline.runner import run_source


def main() -> None:
    """Giao diện dòng lệnh CLI điều phối luồng Data Pipeline."""
    parser = argparse.ArgumentParser(prog="python -m src.pipeline.cli")
    sub = parser.add_subparsers(dest="command")

    # Sub-command: list
    sub.add_parser("list", help="Liệt kê danh sách các nguồn dữ liệu khả dụng")

    # Sub-command: run
    p_run = sub.add_parser("run", help="Thực thi Pipeline cho một hoặc nhiều nguồn dữ liệu")
    p_run.add_argument("--source", action="append", default=[], help="Tên nguồn dữ liệu (có thể lặp lại)")
    p_run.add_argument("--all", action="store_true", help="Thực thi tất cả các nguồn dữ liệu")
    p_run.add_argument("--date", type=str, default=None, help="Ngày thực thi YYYY-MM-DD (Bắt buộc)")
    p_run.add_argument("--dry-run", action="store_true", help="Chạy thử nghiệm (chỉ kiểm định, không ghi dữ liệu)")

    args = parser.parse_args()

    if args.command == "list":
        sources = list_sources()
        if not sources:
            print("Không tìm thấy tệp cấu hình nguồn nào trong sources/*.yaml")
            return

        print(f"{'source':<12} {'type':<10} {'schedule':<10} {'entities':<30} {'contract':<35} {'valid'}")
        print("-" * 110)
        for s in sources:
            print(
                f"{s['name']:<12} {s['type']:<10} {s['schedule']:<10} "
                f"{','.join(s['entities']):<30} {s['contract']:<35} {s['valid']}"
            )
            if not s["valid"]:
                print(f"  LỖI: {s.get('error', '')}")
        return

    if args.command == "run":
        if not args.date:
            print("LỖI: Tham số --date YYYY-MM-DD là bắt buộc", file=sys.stderr)
            sys.exit(1)

        if args.all:
            source_names = get_available_source_names()
        elif args.source:
            source_names = list(args.source)
        else:
            print("LỖI: Cần truyền tham số --source <tên_nguồn> hoặc --all", file=sys.stderr)
            sys.exit(1)

        if not source_names:
            print("Không tìm thấy nguồn dữ liệu phù hợp.", file=sys.stderr)
            sys.exit(1)

        print(f"Đang thực thi các nguồn: {source_names} | batch_date={args.date} | dry_run={args.dry_run}")
        failures: list[str] = []

        for src in source_names:
            try:
                run_source(src, args.date, dry_run=args.dry_run)
            except Exception as e:
                print(f"[{src}] THẤT BẠI: {e}", file=sys.stderr)
                traceback.print_exc()
                failures.append(src)

        if failures:
            print(f"\nDanh sách nguồn thất bại: {failures}", file=sys.stderr)
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
