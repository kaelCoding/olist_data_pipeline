"""pipeline.py - Điều phối toàn bộ quy trình Olist Data Pipeline.

Các bước:
    1. THU THẬP  – crawl Wikipedia API (27 bang Brazil)
    2. LÀM SẠCH – chuẩn hóa 8 bảng Olist + bảng bang IBGE
    3. KIỂM TRA  – PK, FK, domain, dates, completeness, outlier IQR
    4. LƯU       – CSV (và Parquet tùy chọn) + cleaning_report.json

Cách chạy:
    python pipeline.py --olist-dir olist
    python pipeline.py --olist-dir olist --skip-api
    python pipeline.py --olist-dir olist --out my_output --format parquet
    python pipeline.py --olist-dir olist --report-out reports/run1.json
    python pipeline.py --olist-dir olist --log-level DEBUG
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

import pandas as pd

from config import FILES, KEYS
from data_cleaner import clean_olist
from data_crawler import DataCrawler
from data_validator import DataValidator

# ── Thiết lập logging ─────────────────────────────────────────────────────────

def _setup_logging(level: str, log_file: str) -> logging.Logger:
    numeric = getattr(logging, level.upper(), logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(numeric)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    for h in handlers:
        h.setFormatter(fmt)
        root.addHandler(h)
    return logging.getLogger("pipeline")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="pipeline",
        description="Olist Data Pipeline – Thu thập, làm sạch, kiểm tra dữ liệu.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--olist-dir",   required=True,
                    help="Thư mục chứa các file CSV tải từ Kaggle")
    ap.add_argument("--out",         default="data",
                    help="Thư mục đầu ra gốc")
    ap.add_argument("--format",      default="csv", choices=["csv", "parquet", "both"],
                    help="Định dạng file đầu ra cho bảng đã làm sạch")
    ap.add_argument("--skip-api",    action="store_true",
                    help="Bỏ qua bước crawl API (dùng file ibge_states_raw.csv đã lưu)")
    ap.add_argument("--report-out",  default="cleaning_report.json",
                    help="Đường dẫn file báo cáo JSON")
    ap.add_argument("--log-file",    default="crawl_logs.txt",
                    help="Đường dẫn file log (rỗng = không ghi file)")
    ap.add_argument("--log-level",   default="INFO",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                    help="Mức độ chi tiết log")
    return ap.parse_args(argv)


# ── Bước 1: Thu thập ─────────────────────────────────────────────────────────

def step_collect(args: argparse.Namespace, raw_dir: Path, log: logging.Logger) -> pd.DataFrame:
    crawler = DataCrawler(raw_dir=raw_dir, log_file=args.log_file)
    if args.skip_api:
        csv_path = raw_dir / "ibge_states_raw.csv"
        if not csv_path.exists():
            log.error("--skip-api được bật nhưng không tìm thấy %s", csv_path)
            sys.exit(1)
        log.info("--skip-api: đọc %s", csv_path)
        return pd.read_csv(csv_path)
    return crawler.fetch_states()


def step_read_olist(args: argparse.Namespace, raw_dir: Path, log: logging.Logger) -> dict[str, pd.DataFrame]:
    olist_dir = Path(args.olist_dir)
    raw: dict[str, pd.DataFrame] = {}
    for fname, table in FILES.items():
        src = olist_dir / fname
        if not src.exists():
            log.error("Không tìm thấy file: %s", src)
            sys.exit(1)
        shutil.copy2(src, raw_dir / fname)
        raw[table] = pd.read_csv(raw_dir / fname)
        log.info("Đọc %-22s %s dòng", table, f"{len(raw[table]):,}")
    return raw


# ── Bước 2: Làm sạch ─────────────────────────────────────────────────────────

def step_clean(raw: dict, ibge: pd.DataFrame) -> tuple[dict, dict]:
    clean, report = clean_olist(raw)

    ibge_clean = ibge.drop_duplicates().copy()
    for c in ("state_code", "region_code"):
        ibge_clean[c] = ibge_clean[c].str.strip().str.upper()
    for c in ("state_name", "region_name"):
        ibge_clean[c] = ibge_clean[c].str.strip()

    report["ibge_states"] = {
        "rows_in":  int(len(ibge)),
        "rows_out": int(len(ibge_clean)),
    }
    return clean, ibge_clean, report


# ── Bước 3: Kiểm tra ─────────────────────────────────────────────────────────

def step_validate(clean: dict, ibge_clean: pd.DataFrame) -> dict:
    return DataValidator(clean, ibge_clean).run(KEYS)


# ── Bước 4: Lưu kết quả ──────────────────────────────────────────────────────

def _save_df(df: pd.DataFrame, stem: str, clean_dir: Path, fmt: str) -> None:
    """Lưu DataFrame theo định dạng csv / parquet / both."""
    if fmt in ("csv", "both"):
        df.to_csv(clean_dir / f"{stem}.csv", index=False, encoding="utf-8")
    if fmt in ("parquet", "both"):
        try:
            df.to_parquet(clean_dir / f"{stem}.parquet", index=False)
        except ImportError:
            logging.getLogger("pipeline").warning(
                "pyarrow chưa cài – bỏ qua Parquet cho %s. "
                "Chạy: pip install pyarrow", stem,
            )


def step_save(
    clean: dict,
    ibge_clean: pd.DataFrame,
    report: dict,
    validation: dict,
    clean_dir: Path,
    report_path: Path,
    fmt: str,
) -> None:
    clean_dir.mkdir(parents=True, exist_ok=True)
    for table, df in clean.items():
        _save_df(df, f"{table}_clean", clean_dir, fmt)
    _save_df(ibge_clean, "ibge_states_clean", clean_dir, fmt)

    # JSON phụ (luôn lưu)
    ibge_clean.to_json(clean_dir / "ibge_states_clean.json",
                       orient="records", force_ascii=False, indent=2)

    report_path.write_text(
        json.dumps({"cleaning": report, "validation": validation},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


# ── In báo cáo terminal ───────────────────────────────────────────────────────

def _print_report(report: dict, validation: dict) -> None:
    print(f"\n{'Bảng':<22}{'Dòng thô':>10}{'Dòng sạch':>11}{'Trùng bỏ':>10}")
    print("-" * 53)
    for t, r in report.items():
        if t == "ibge_states":
            continue
        d = r["steps"]["duplicates"]
        removed = d["exact_rows_removed"] + d["key_duplicates_removed"]
        print(f"{t:<22}{r['rows_in']:>10,}{r['rows_out']:>11,}{removed:>10,}")

    print(f"\nKiểm tra: {validation['summary']}")
    for r in validation["rules"]:
        if r["status"] != "PASS":
            pct = r["violations"] / r["checked"] * 100 if r["checked"] else 0
            print(
                f"  [{r['status']}] {r['rule']}: "
                f"{r['violations']:,}/{r['checked']:,} ({pct:.2f}%) - {r['description']}"
            )

    out = validation["outliers"]
    print("\nOutlier IQR:")
    for key, v in out.items():
        print(f"  {key}: above_fence={v['above_fence']:,}  max={v['max']:.2f}  "
              f"fence={v['upper_fence']:.2f}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv=None) -> None:
    args = _parse_args(argv)
    log = _setup_logging(args.log_level, args.log_file)

    raw_dir   = Path(args.out) / "raw"
    clean_dir = Path(args.out) / "clean"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 1. Thu thập
    ibge = step_collect(args, raw_dir, log)
    raw  = step_read_olist(args, raw_dir, log)

    # 2. Làm sạch
    clean, ibge_clean, report = step_clean(raw, ibge)

    # 3. Kiểm tra
    validation = step_validate(clean, ibge_clean)

    # 4. Lưu
    step_save(clean, ibge_clean, report, validation,
              clean_dir, Path(args.report_out), args.format)

    # In tóm tắt
    _print_report(report, validation)

    log.info("✔ Pipeline hoàn thành. Báo cáo: %s", args.report_out)

    # Exit code phản ánh kết quả
    n_fail = validation["summary"]["FAIL"]
    if n_fail > 0:
        log.error("%s quy tắc FAIL – kiểm tra cleaning_report.json", n_fail)
        sys.exit(1)


if __name__ == "__main__":
    main()
