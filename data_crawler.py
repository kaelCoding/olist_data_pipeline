"""data_crawler.py - Thu thập dữ liệu bổ sung từ API công khai cho đề tài Olist.

Chiến lược đa nguồn (thứ tự ưu tiên):
  1. Wikipedia MediaWiki API  – nguồn chính, không cần API key.
     Endpoint: https://en.wikipedia.org/w/api.php
  2. IBGE Localidades API     – nguồn dự phòng chính thức của Brazil.
     Endpoint: https://servicodados.ibge.gov.br/api/v1/localidades/estados
  3. Embedded fallback        – dữ liệu tĩnh nhúng sẵn, dùng khi offline.

Mục đích: cung cấp bảng ánh xạ state_code ↔ region cho các phân tích RQ2/RQ3.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from config import (
    IBGE_STATES_URL,
    IBGE_STATES_FALLBACK,
    STATE_REGION,
    WIKIPEDIA_API_URL,
)

# ── Logger mặc định (pipeline.py có thể override) ─────────────────────────────
log = logging.getLogger("crawler")


class DataCrawler:
    """Thu thập dữ liệu bổ sung từ nhiều nguồn API, có retry & fallback."""

    def __init__(
        self,
        raw_dir: str | Path = "data/raw",
        log_file: str = "crawl_logs.txt",
        retries: int = 3,
        timeout: int = 15,
        backoff: float = 2.0,
    ):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.retries = retries
        self.timeout = timeout
        self.backoff = backoff

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "OlistPipeline/2.0 (academic; github.com/kaelCoding/olist_data_pipeline)"
        })

        # Thiết lập logger nếu chưa có handler
        if not log.handlers:
            log.setLevel(logging.INFO)
            fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
            handlers: list[logging.Handler] = [logging.StreamHandler()]
            if log_file:
                handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
            for h in handlers:
                h.setFormatter(fmt)
                log.addHandler(h)

        self.log = log

    # ── HTTP helper ────────────────────────────────────────────────────────────

    def fetch_json(
        self,
        url: str,
        params: Optional[dict] = None,
        method: str = "GET",
        json_body: Optional[dict] = None,
    ) -> tuple[dict, dict]:
        """GET/POST với exponential-backoff retry.

        Returns:
            (parsed_json, request_info_dict)
        Raises:
            requests.RequestException nếu hết lần thử.
        """
        for attempt in range(1, self.retries + 1):
            try:
                t0 = time.time()
                if method == "POST":
                    resp = self.session.post(
                        url, params=params, json=json_body, timeout=self.timeout
                    )
                else:
                    resp = self.session.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                elapsed = round(time.time() - t0, 2)
                nbytes = len(resp.content)
                info = {
                    "url":    resp.url,
                    "status": resp.status_code,
                    "seconds": elapsed,
                    "bytes":  nbytes,
                    "sha256": hashlib.sha256(resp.content).hexdigest(),
                }
                self.log.info("OK %s (HTTP %s, %s bytes)", resp.url, resp.status_code, nbytes)
                return resp.json(), info
            except (requests.RequestException, ValueError) as exc:
                self.log.warning("Lần %s/%s lỗi: %s", attempt, self.retries, exc)
                if attempt == self.retries:
                    self.log.error("Bỏ cuộc sau %s lần: %s", self.retries, url)
                    raise
                time.sleep(self.backoff ** attempt)
        raise RuntimeError("fetch_json: thoát vòng lặp không mong đợi")  # pragma: no cover

    # ── Parsers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _flatten_ibge(data: list[dict]) -> pd.DataFrame:
        """Làm phẳng JSON IBGE (state → regiao) thành bảng 1 dòng/bang."""
        return pd.DataFrame([
            {
                "state_id":    s["id"],
                "state_code":  s["sigla"],
                "state_name":  s["nome"],
                "region_id":   s["regiao"]["id"],
                "region_code": s["regiao"]["sigla"],
                "region_name": s["regiao"]["nome"],
            }
            for s in data
        ])

    @staticmethod
    def _parse_wikipedia_wikitext(wikitext: str) -> pd.DataFrame:
        """Parse bảng bang Brazil từ Wikipedia wikitext.

        Định dạng mỗi dòng (ví dụ):
            ! scope=row | {{flag|Acre}}
            | AC || [[Rio Branco, Acre|Rio Branco]] || ...
        """
        entries = re.findall(
            r'! scope=row \| (?:\{\{nowrap\|)?\{\{flag\|([^}]+)\}\}\}*\s*\n\|\s*([A-Z]{2})\s*\|',
            wikitext,
        )
        if not entries:
            raise ValueError("Không tìm được bảng bang trong Wikipedia wikitext")

        rows = []
        for state_name, code in entries:
            state_name = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', state_name).strip()
            code = code.strip()
            if code not in STATE_REGION:
                continue
            region_code, region_name = STATE_REGION[code]
            rows.append({
                "state_id":    None,
                "state_code":  code,
                "state_name":  state_name,
                "region_id":   None,
                "region_code": region_code,
                "region_name": region_name,
            })

        df = pd.DataFrame(rows)
        if len(df) < 20:
            raise ValueError(f"Chỉ parse được {len(df)} bang, kỳ vọng ≥ 27")
        return df.drop_duplicates(subset="state_code").reset_index(drop=True)

    # ── Nguồn 1: Wikipedia MediaWiki API ──────────────────────────────────────

    def fetch_wikipedia_states(self) -> tuple[pd.DataFrame, dict]:
        """Lấy danh sách bang Brazil từ Wikipedia (không cần API key)."""
        self.log.info("Đang lấy dữ liệu bang từ Wikipedia MediaWiki API...")
        params = {
            "action":        "query",
            "prop":          "revisions",
            "rvprop":        "content",
            "titles":        "Federative_units_of_Brazil",
            "format":        "json",
            "formatversion": 2,
            "rvslots":       "main",
        }
        data, info = self.fetch_json(WIKIPEDIA_API_URL, params=params)
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            raise ValueError("Wikipedia API không trả về trang nào")
        wikitext = (
            pages[0]
            .get("revisions", [{}])[0]
            .get("slots", {})
            .get("main", {})
            .get("content", "")
        )
        if not wikitext:
            raise ValueError("Wikipedia không trả về nội dung wikitext")
        df = self._parse_wikipedia_wikitext(wikitext)
        self.log.info("Wikipedia: parse được %s bang", len(df))
        return df, info

    # ── Nguồn 2: IBGE Localidades API ─────────────────────────────────────────

    def fetch_ibge_states_raw(self) -> tuple[pd.DataFrame, dict, list]:
        """Lấy 27 bang trực tiếp từ API IBGE chính thức."""
        self.log.info("Đang thử IBGE Localidades API...")
        data, info = self.fetch_json(IBGE_STATES_URL, params={"orderBy": "nome"})
        df = self._flatten_ibge(data)
        self.log.info("IBGE API: nhận %s bang", len(df))
        return df, info, data

    # ── Nguồn 3: Embedded fallback ─────────────────────────────────────────────

    def _use_embedded_fallback(self) -> pd.DataFrame:
        self.log.warning("⚠  Dùng dữ liệu 27 bang nhúng sẵn (offline fallback).")
        return pd.DataFrame(IBGE_STATES_FALLBACK)

    # ── Entry point chính ──────────────────────────────────────────────────────

    def fetch_states(self) -> pd.DataFrame:
        """Thu thập bảng 27 bang Brazil, thử Wikipedia → IBGE → Fallback.

        Luôn lưu kết quả vào ``raw_dir/`` kèm metadata.
        """
        source_name = "unknown"
        raw_json: list | None = None
        df: pd.DataFrame | None = None
        info: dict = {}

        # 1. Wikipedia
        try:
            df, info = self.fetch_wikipedia_states()
            source_name = "wikipedia_mediawiki_api"
            raw_json = df.to_dict(orient="records")
        except Exception as exc:
            self.log.warning("Wikipedia thất bại: %s – thử IBGE...", exc)

        # 2. IBGE
        if df is None:
            try:
                df, info, raw_json = self.fetch_ibge_states_raw()
                source_name = IBGE_STATES_URL
            except Exception as exc:
                self.log.warning("IBGE thất bại: %s – dùng embedded fallback.", exc)

        # 3. Embedded fallback
        if df is None:
            df = self._use_embedded_fallback()
            source_name = "embedded_fallback"
            raw_json = IBGE_STATES_FALLBACK

        # Lưu kết quả
        (self.raw_dir / "ibge_states_raw.json").write_text(
            json.dumps(raw_json, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        df.to_csv(self.raw_dir / "ibge_states_raw.csv", index=False, encoding="utf-8")

        meta = {
            "source":         source_name,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "records":        int(len(df)),
            **info,
        }
        (self.raw_dir / "crawl_metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        self.log.info("✔ Đã lưu %s bang từ nguồn '%s' vào %s", len(df), source_name, self.raw_dir)
        return df

    # ── Backward-compatible alias ──────────────────────────────────────────────

    def fetch_ibge_states(self) -> pd.DataFrame:
        """Alias giữ tương thích ngược với pipeline cũ."""
        return self.fetch_states()
