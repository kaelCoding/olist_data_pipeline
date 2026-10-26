"""data_validator.py - Kiểm tra chất lượng dữ liệu sau khi làm sạch.

Kiểm tra đầy đủ: khóa chính (PK), khóa ngoại (FK), miền giá trị (DOM),
thứ tự thời gian (DATE), độ hoàn chỉnh (MISS), và phân tích outlier (IQR).

Dùng được độc lập:
    from data_validator import DataValidator
    result = DataValidator(clean_tables, ibge_df).run(KEYS)
"""
from __future__ import annotations

import pandas as pd

from config import ORDER_STATUS, PAYMENT_TYPES


class DataValidator:
    """Chạy bộ kiểm tra chất lượng trên dict các bảng đã làm sạch."""

    def __init__(
        self,
        tables: dict[str, pd.DataFrame],
        ibge_states: pd.DataFrame | None = None,
    ):
        self.t = tables
        self.ibge = ibge_states
        self.results: list[dict] = []

    # ── Helper nội bộ ─────────────────────────────────────────────────────────

    def _add(
        self,
        rule: str,
        desc: str,
        bad: int,
        total: int,
        severity: str = "error",
    ) -> None:
        bad = int(bad)
        status = "PASS" if bad == 0 else ("FAIL" if severity == "error" else "WARN")
        self.results.append({
            "rule":        rule,
            "description": desc,
            "violations":  bad,
            "checked":     int(total),
            "status":      status,
        })

    # ── Kiểm tra PK ──────────────────────────────────────────────────────────

    def check_keys(self, keys: dict[str, list[str]]) -> "DataValidator":
        """PK: mỗi khóa chính phải duy nhất và không NULL."""
        for name, key in keys.items():
            df = self.t[name]
            bad = df.duplicated(subset=key).sum() + df[key].isna().any(axis=1).sum()
            self._add(
                f"PK:{name}",
                f"Khóa chính {key} duy nhất và không NULL",
                bad, len(df),
            )
        return self

    # ── Kiểm tra FK ──────────────────────────────────────────────────────────

    def check_foreign_keys(self) -> "DataValidator":
        """FK: mỗi giá trị phải tồn tại trong bảng cha."""
        fks = [
            ("orders",       "customer_id", "customer"),
            ("order_item",   "order_id",    "orders"),
            ("order_item",   "product_id",  "product"),
            ("order_item",   "seller_id",   "seller"),
            ("order_payment","order_id",    "orders"),
            ("order_review", "order_id",    "orders"),
        ]
        for child, col, parent in fks:
            bad = ~self.t[child][col].isin(self.t[parent][col])
            self._add(
                f"FK:{child}.{col}",
                f"{child}.{col} tồn tại trong {parent}",
                bad.sum(), len(bad),
            )
        return self

    # ── Kiểm tra domain ───────────────────────────────────────────────────────

    def check_domains(self) -> "DataValidator":
        """DOM: miền giá trị hợp lệ cho các cột phân loại và số."""
        o = self.t["orders"]
        i = self.t["order_item"]
        p = self.t["order_payment"]
        r = self.t["order_review"]

        self._add("DOM:order_status",
                  "order_status thuộc tập trạng thái hợp lệ",
                  (~o["order_status"].isin(ORDER_STATUS)).sum(), len(o))

        self._add("DOM:price",
                  "price > 0",
                  (i["price"] <= 0).sum(), len(i))

        self._add("DOM:freight",
                  "freight_value >= 0",
                  (i["freight_value"] < 0).sum(), len(i))

        self._add("DOM:payment_value",
                  "payment_value >= 0",
                  (p["payment_value"] < 0).sum(), len(p))

        self._add("DOM:payment_type",
                  "payment_type thuộc tập hình thức hợp lệ",
                  (~p["payment_type"].isin(PAYMENT_TYPES)).sum(), len(p))

        self._add("DOM:installments",
                  "payment_installments >= 1 (0 là bất thường, giữ lại để theo dõi)",
                  (p["payment_installments"] < 1).sum(), len(p), "warning")

        self._add("DOM:not_defined",
                  "payment_type = not_defined (giữ lại, loại ở RQ1 nếu cần)",
                  (p["payment_type"] == "not_defined").sum(), len(p), "warning")

        self._add("DOM:review_score",
                  "review_score thuộc 1..5",
                  (~r["review_score"].between(1, 5)).sum(), len(r))

        # Kiểm tra mã bang đối chiếu IBGE
        if self.ibge is not None:
            codes = set(self.ibge["state_code"])
            for tbl, col in (("customer", "customer_state"), ("seller", "seller_state")):
                self._add(
                    f"DOM:{col}",
                    f"{col} nằm trong 27 mã bang của IBGE",
                    (~self.t[tbl][col].isin(codes)).sum(), len(self.t[tbl]),
                )
        return self

    # ── Kiểm tra thứ tự thời gian ────────────────────────────────────────────

    def check_dates(self) -> "DataValidator":
        """DATE: thứ tự logic giữa các mốc thời gian trong vòng đời đơn hàng."""
        o = self.t["orders"]
        pairs = [
            ("order_approved_at",            "order_purchase_timestamp"),
            ("order_delivered_carrier_date", "order_approved_at"),
            ("order_delivered_customer_date","order_delivered_carrier_date"),
        ]
        for later, earlier in pairs:
            both = o[later].notna() & o[earlier].notna()
            self._add(
                f"DATE:{later}",
                f"{later} >= {earlier}",
                (o.loc[both, later] < o.loc[both, earlier]).sum(), both.sum(), "warning",
            )
        deliv = o["order_status"] == "delivered"
        self._add(
            "DATE:delivered_null",
            "Đơn delivered nhưng thiếu ngày giao thực tế (loại khỏi RQ3)",
            (deliv & o["order_delivered_customer_date"].isna()).sum(), deliv.sum(), "warning",
        )
        return self

    # ── Kiểm tra tính hoàn chỉnh ─────────────────────────────────────────────

    def check_completeness(self) -> "DataValidator":
        """MISS: không còn NULL ở các cột quan trọng sau khi điền."""
        p = self.t["product"]
        self._add("MISS:category",
                  "Không còn danh mục NULL sau khi điền 'unknown'",
                  p["product_category_name"].isna().sum(), len(p))
        self._add("MISS:category_en",
                  "Mọi sản phẩm có tên danh mục tiếng Anh",
                  p["product_category_name_english"].isna().sum(), len(p))
        return self

    # ── Phân tích outlier IQR ─────────────────────────────────────────────────

    def outliers_iqr(self) -> dict:
        """Tính IQR fence cho các cột giá trị; không xóa, chỉ gắn nhãn."""
        out: dict = {}
        for tbl, col in (
            ("order_item",    "price"),
            ("order_item",    "freight_value"),
            ("order_payment", "payment_value"),
        ):
            s = self.t[tbl][col].dropna()
            q1, q3 = s.quantile([0.25, 0.75])
            hi = q3 + 1.5 * (q3 - q1)
            out[f"{tbl}.{col}"] = {
                "q1":          float(q1),
                "q3":          float(q3),
                "upper_fence": float(hi),
                "above_fence": int((s > hi).sum()),
                "max":         float(s.max()),
                "action":      "giữ lại (không xóa), chỉ gắn nhãn khi báo cáo AOV",
            }
        return out

    # ── Thống kê tổng hợp ────────────────────────────────────────────────────

    def summary(self) -> dict[str, int]:
        return {s: sum(r["status"] == s for r in self.results) for s in ("PASS", "WARN", "FAIL")}

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(self, keys: dict[str, list[str]]) -> dict:
        """Chạy toàn bộ kiểm tra và trả về kết quả tổng hợp.

        Returns:
            dict gồm: ``summary``, ``rules``, ``outliers``.
        """
        (
            self.check_keys(keys)
                .check_foreign_keys()
                .check_domains()
                .check_dates()
                .check_completeness()
        )
        return {
            "summary":  self.summary(),
            "rules":    self.results,
            "outliers": self.outliers_iqr(),
        }
