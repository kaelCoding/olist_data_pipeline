"""data_cleaner.py - Làm sạch và chuẩn hóa 8 bảng Olist + bảng bang/vùng IBGE.

Nguyên tắc thiết kế:
- Mỗi bước ghi lại số dòng/ô bị tác động để xuất cleaning_report.json.
- Không xóa dòng chỉ vì có NULL; chỉ điền khi cột phục vụ trực tiếp RQ1-RQ3.
- API fluent (method chaining) giúp recipe của từng bảng ngắn gọn và dễ đọc.
- Mọi hằng số (FILES, KEYS, MANUAL_TRANSLATION) chuyển vào config.py.
"""
from __future__ import annotations

import pandas as pd

from config import FILES, KEYS, MANUAL_TRANSLATION


class DataCleaner:
    """Builder pattern: áp dụng từng bước làm sạch và ghi audit report."""

    def __init__(self, name: str, df: pd.DataFrame, key: list[str] | None = None):
        self.name = name
        self.df = df.copy()
        self.key = key
        self.report: dict = {
            "table":   name,
            "rows_in": int(len(df)),
            "steps":   {},
        }

    # ── 1. Xóa trùng lặp ──────────────────────────────────────────────────────

    def drop_duplicates(self) -> "DataCleaner":
        """Xóa dòng trùng toàn bộ, sau đó trùng khóa chính (giữ dòng cuối)."""
        n0 = len(self.df)
        self.df = self.df.drop_duplicates()
        exact = n0 - len(self.df)
        by_key = 0
        if self.key:
            n1 = len(self.df)
            self.df = self.df.drop_duplicates(subset=self.key, keep="last")
            by_key = n1 - len(self.df)
        self.report["steps"]["duplicates"] = {
            "exact_rows_removed":  int(exact),
            "key_duplicates_removed": int(by_key),
        }
        return self

    # ── 2. Chuẩn hóa văn bản ─────────────────────────────────────────────────

    def clean_text(self, cols: list[str], case: str | None = None) -> "DataCleaner":
        """Strip khoảng trắng, áp case, đổi chuỗi rỗng → NULL."""
        blanks = 0
        for c in cols:
            s = self.df[c].astype("string").str.strip()
            if case == "lower":
                s = s.str.lower()
            elif case == "upper":
                s = s.str.upper()
            blanks += int((s == "").sum())
            self.df[c] = s.replace("", pd.NA)
        self.report["steps"].setdefault("text", {})[",".join(cols)] = {
            "case": case,
            "blank_to_null": blanks,
        }
        return self

    # ── 3. Chuyển kiểu dữ liệu ───────────────────────────────────────────────

    def to_datetime(self, cols: list[str]) -> "DataCleaner":
        """Parse sang datetime64; giá trị không hợp lệ → NaT."""
        for c in cols:
            before = int(self.df[c].isna().sum())
            self.df[c] = pd.to_datetime(self.df[c], errors="coerce")
            self.report["steps"].setdefault("datetime", {})[c] = {
                "invalid_to_null": int(self.df[c].isna().sum()) - before,
            }
        return self

    def to_numeric(
        self,
        cols: list[str],
        decimals: int | None = None,
        integer: bool = False,
    ) -> "DataCleaner":
        """Parse sang số; tùy chọn làm tròn hoặc ép kiểu Int64 (nullable)."""
        for c in cols:
            before = int(self.df[c].isna().sum())
            self.df[c] = pd.to_numeric(self.df[c], errors="coerce")
            if decimals is not None:
                self.df[c] = self.df[c].round(decimals)
            if integer:
                self.df[c] = self.df[c].round().astype("Int64")
            self.report["steps"].setdefault("numeric", {})[c] = {
                "invalid_to_null": int(self.df[c].isna().sum()) - before,
            }
        return self

    # ── 4. Xử lý dữ liệu thiếu ───────────────────────────────────────────────

    def fill_value(self, col: str, value) -> "DataCleaner":
        """Điền NULL bằng một giá trị cố định."""
        n = int(self.df[col].isna().sum())
        self.df[col] = self.df[col].fillna(value)
        self.report["steps"].setdefault("filled", {})[col] = {
            "value": value, "cells": n,
        }
        return self

    def fill_group_median(self, cols: list[str], by: str) -> "DataCleaner":
        """Điền NULL bằng median theo nhóm; nếu nhóm vẫn NULL thì dùng median toàn bảng."""
        for c in cols:
            n = int(self.df[c].isna().sum())
            med = self.df.groupby(by)[c].transform("median")
            self.df[c] = self.df[c].fillna(med).fillna(self.df[c].median())
            self.report["steps"].setdefault("filled", {})[c] = {
                "value": f"median theo {by}", "cells": n,
            }
        return self

    # ── 5. Kết thúc & trả kết quả ────────────────────────────────────────────

    def finish(self) -> tuple[pd.DataFrame, dict]:
        """Trả về (DataFrame sạch, audit report dict)."""
        miss = self.df.isna().sum()
        self.report["rows_out"] = int(len(self.df))
        self.report["missing_after"] = {k: int(v) for k, v in miss.items() if v}
        return self.df, self.report


# ── Recipe làm sạch cho từng bảng ─────────────────────────────────────────────

def _clean_customer(c: DataCleaner) -> DataCleaner:
    return (
        c.drop_duplicates()
         .clean_text(["customer_id", "customer_unique_id"])
         .clean_text(["customer_city"], "lower")
         .clean_text(["customer_state"], "upper")
         .to_numeric(["customer_zip_code_prefix"], integer=True)
    )


def _clean_seller(c: DataCleaner) -> DataCleaner:
    return (
        c.drop_duplicates()
         .clean_text(["seller_id"])
         .clean_text(["seller_city"], "lower")
         .clean_text(["seller_state"], "upper")
         .to_numeric(["seller_zip_code_prefix"], integer=True)
    )


def _clean_category_translation(c: DataCleaner) -> DataCleaner:
    return (
        c.drop_duplicates()
         .clean_text(["product_category_name", "product_category_name_english"], "lower")
    )


def _clean_product(c: DataCleaner, category_translation_df: pd.DataFrame) -> DataCleaner:
    dims = ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]
    (
        c.drop_duplicates()
         .clean_text(["product_id"])
         .clean_text(["product_category_name"], "lower")
         .to_numeric(dims)
         .to_numeric(
             ["product_name_lenght", "product_description_lenght", "product_photos_qty"],
             integer=True,
         )
         .fill_value("product_category_name", "unknown")
         .fill_group_median(dims, "product_category_name")
    )
    # Gắn tên danh mục tiếng Anh (LEFT JOIN + bản dịch thủ công)
    tr = category_translation_df.set_index("product_category_name")["product_category_name_english"]
    mapping = {**tr.to_dict(), **{k: v for k, v in MANUAL_TRANSLATION.items() if k not in tr.index}}
    eng = c.df["product_category_name"].map(mapping)
    c.report["steps"]["english_category_unmapped"] = int(eng.isna().sum())
    c.df["product_category_name_english"] = eng.fillna("unknown")
    return c


def _clean_orders(c: DataCleaner) -> DataCleaner:
    return (
        c.drop_duplicates()
         .clean_text(["order_id", "customer_id"])
         .clean_text(["order_status"], "lower")
         .to_datetime([
             "order_purchase_timestamp", "order_approved_at",
             "order_delivered_carrier_date", "order_delivered_customer_date",
             "order_estimated_delivery_date",
         ])
    )


def _clean_order_item(c: DataCleaner) -> DataCleaner:
    return (
        c.drop_duplicates()
         .clean_text(["order_id", "product_id", "seller_id"])
         .to_datetime(["shipping_limit_date"])
         .to_numeric(["order_item_id"], integer=True)
         .to_numeric(["price", "freight_value"], decimals=2)
    )


def _clean_order_payment(c: DataCleaner) -> DataCleaner:
    return (
        c.drop_duplicates()
         .clean_text(["order_id"])
         .clean_text(["payment_type"], "lower")
         .to_numeric(["payment_sequential", "payment_installments"], integer=True)
         .to_numeric(["payment_value"], decimals=2)
    )


def _clean_order_review(c: DataCleaner) -> DataCleaner:
    return (
        c.drop_duplicates()
         .clean_text(["review_id", "order_id"])
         .clean_text(["review_comment_title", "review_comment_message"])
         .to_numeric(["review_score"], integer=True)
         .to_datetime(["review_creation_date", "review_answer_timestamp"])
    )


# ── Entry point ────────────────────────────────────────────────────────────────

def clean_olist(
    raw: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    """Làm sạch tất cả 8 bảng Olist.

    Args:
        raw: dict ``{table_name: DataFrame}`` từ bước đọc file.

    Returns:
        ``(clean_tables, cleaning_report)``
    """
    out: dict[str, pd.DataFrame] = {}
    rep: dict[str, dict] = {}

    def run(name: str, builder) -> None:
        cleaner = DataCleaner(name, raw[name], KEYS[name])
        out[name], rep[name] = builder(cleaner).finish()

    run("customer",            _clean_customer)
    run("seller",              _clean_seller)
    run("category_translation", _clean_category_translation)

    # product cần bảng category_translation đã sạch
    c_product = DataCleaner("product", raw["product"], KEYS["product"])
    out["product"], rep["product"] = _clean_product(c_product, out["category_translation"]).finish()

    run("orders",              _clean_orders)
    run("order_item",          _clean_order_item)
    run("order_payment",       _clean_order_payment)
    run("order_review",        _clean_order_review)

    return out, rep
