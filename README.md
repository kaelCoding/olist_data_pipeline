# Olist Data Pipeline

> **Data Engineering · DBI Course – Week 7**  
> Thu thập → Làm sạch → Kiểm tra chất lượng dữ liệu thương mại điện tử Olist (Brazil)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![pandas](https://img.shields.io/badge/pandas-2.0%2B-150458?logo=pandas)](https://pandas.pydata.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Mục lục

- [Tổng quan](#tổng-quan)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Kết quả pipeline](#kết-quả-pipeline)
- [Cài đặt](#cài-đặt)
- [Cách chạy](#cách-chạy)
- [Tham số CLI](#tham-số-cli)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Mô tả các module](#mô-tả-các-module)
- [Chiến lược thu thập dữ liệu](#chiến-lược-thu-thập-dữ-liệu)
- [Quy trình làm sạch](#quy-trình-làm-sạch)
- [Bộ kiểm tra chất lượng](#bộ-kiểm-tra-chất-lượng)
- [Báo cáo đầu ra](#báo-cáo-đầu-ra)

---

## Tổng quan

Pipeline xử lý **~630 000 dòng** từ 8 bảng Kaggle Olist kết hợp với dữ liệu bang Brazil crawl từ API công khai. Toàn bộ quy trình gồm 4 bước tự động:

```
[Kaggle CSV] ──► CRAWL API ──► CLEAN ──► VALIDATE ──► SAVE (CSV / Parquet)
                    │                        │
                Wikipedia / IBGE          cleaning_report.json
                (27 bang Brazil)
```

---

## Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────┐
│                     pipeline.py                         │
│   step_collect → step_read_olist → step_clean           │
│               → step_validate → step_save               │
└────┬──────────────┬──────────────┬──────────────────────┘
     │              │              │
     ▼              ▼              ▼
data_crawler   data_cleaner   data_validator
     │              │              │
     └──────────────┴──── config.py (hằng số dùng chung)
```

| Module | Trách nhiệm |
|---|---|
| `config.py` | Hằng số tập trung: FILES, KEYS, domain values, API URL |
| `data_crawler.py` | HTTP retry, multi-source (Wikipedia → IBGE → fallback) |
| `data_cleaner.py` | Builder pattern, audit report từng bước |
| `data_validator.py` | 30 quy tắc: PK, FK, DOM, DATE, MISS, IQR outlier |
| `pipeline.py` | CLI, orchestration, logging, save CSV/Parquet |

---

## Kết quả pipeline

### Dữ liệu đầu vào

| Bảng | Dòng thô | Dòng sạch | Trùng bỏ |
|---|---|---|---|
| customer | 99,441 | 99,441 | 0 |
| seller | 3,095 | 3,095 | 0 |
| category_translation | 71 | 71 | 0 |
| product | 32,951 | 32,951 | 0 |
| orders | 99,441 | 99,441 | 0 |
| order_item | 112,650 | 112,650 | 0 |
| order_payment | 103,886 | 103,886 | 0 |
| order_review | 99,224 | 99,224 | 0 |
| ibge_states (API) | 27 | 27 | 0 |

### Kết quả kiểm tra chất lượng

| Kết quả | Số quy tắc |
|---|---|
| ✅ PASS | 25 |
| ⚠️ WARN | 5 |
| ❌ FAIL | 0 |

**5 WARN (đã phân tích, không xóa dữ liệu):**

| Rule | Số vi phạm | Ghi chú |
|---|---|---|
| `DOM:installments` | 2 / 103,886 | `payment_installments = 0` – bất thường, giữ lại theo dõi |
| `DOM:not_defined` | 3 / 103,886 | `payment_type = not_defined` – loại ở phân tích RQ1 nếu cần |
| `DATE:order_delivered_carrier_date` | 1,359 / 97,644 | Ngày giao carrier < ngày duyệt – có thể do data entry |
| `DATE:order_delivered_customer_date` | 23 / 96,475 | Ngày giao KH < ngày giao carrier |
| `DATE:delivered_null` | 8 / 96,478 | Đơn `delivered` nhưng thiếu ngày giao thực tế |

---

## Cài đặt

> Yêu cầu: **Python 3.10+**

```bash
# 1. Tạo virtual environment (chỉ làm 1 lần)
python -m venv .venv

# 2. Kích hoạt venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# 3. Cài thư viện
pip install -r requirements.txt

# (Tùy chọn) Cài pyarrow để xuất Parquet
pip install pyarrow
```

**Chuẩn bị dữ liệu Kaggle:**

Tải dataset [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) và giải nén vào thư mục `olist/`.

---

## Cách chạy

```bash
# Chạy đầy đủ (crawl API + làm sạch + validate, xuất CSV)
python pipeline.py --olist-dir olist

# Bỏ qua crawl API (dùng file ibge_states_raw.csv đã lưu trước)
python pipeline.py --olist-dir olist --skip-api

# Xuất Parquet thay vì CSV
python pipeline.py --olist-dir olist --format parquet

# Xuất cả CSV lẫn Parquet
python pipeline.py --olist-dir olist --format both

# Đổi thư mục output
python pipeline.py --olist-dir olist --out my_output

# Đổi đường dẫn báo cáo JSON
python pipeline.py --olist-dir olist --report-out reports/run_$(date +%Y%m%d).json

# Chạy ở chế độ debug
python pipeline.py --olist-dir olist --log-level DEBUG
```

---

## Tham số CLI

| Tham số | Mặc định | Mô tả |
|---|---|---|
| `--olist-dir` | *(bắt buộc)* | Thư mục chứa file CSV Kaggle |
| `--out` | `data` | Thư mục đầu ra gốc |
| `--format` | `csv` | Định dạng xuất: `csv` / `parquet` / `both` |
| `--skip-api` | `False` | Bỏ qua crawl, dùng file đã lưu |
| `--report-out` | `cleaning_report.json` | Đường dẫn báo cáo JSON |
| `--log-file` | `crawl_logs.txt` | File log (rỗng = không ghi file) |
| `--log-level` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

---

## Cấu trúc dự án

```
olist_data_pipeline/
├── pipeline.py            # Điều phối toàn bộ quy trình (CLI entry point)
├── config.py              # Hằng số dùng chung (FILES, KEYS, URLs, domain sets)
├── data_crawler.py        # Thu thập dữ liệu bang từ API (multi-source + fallback)
├── data_cleaner.py        # Làm sạch 8 bảng Olist (builder pattern + audit log)
├── data_validator.py      # 30 quy tắc kiểm tra chất lượng (PK/FK/DOM/DATE/MISS)
├── requirements.txt       # Thư viện phụ thuộc
├── .gitignore
├── README.md
│
├── olist/                 # ← Dữ liệu gốc Kaggle (không commit git)
│   ├── olist_customers_dataset.csv
│   ├── olist_orders_dataset.csv
│   └── ... (8 file CSV)
│
└── data/                  # ← Sinh ra khi chạy pipeline
    ├── raw/               # Bản gốc sao chép + dữ liệu crawled
    │   ├── olist_*.csv
    │   ├── ibge_states_raw.csv
    │   ├── ibge_states_raw.json
    │   └── crawl_metadata.json
    └── clean/             # Bản đã làm sạch
        ├── *_clean.csv    # (hoặc .parquet tùy --format)
        ├── ibge_states_clean.csv
        └── ibge_states_clean.json
```

---

## Mô tả các module

### `config.py`
Tập trung toàn bộ hằng số: ánh xạ tên file Kaggle → tên bảng, định nghĩa khóa chính, tập hợp domain values (`ORDER_STATUS`, `PAYMENT_TYPES`), URL API, bảng vùng Brazil tĩnh.

### `data_crawler.py`
- **Class `DataCrawler`**: HTTP session với exponential-backoff retry (mặc định 3 lần).
- Chiến lược đa nguồn: Wikipedia → IBGE → Embedded fallback.
- Lưu raw JSON + CSV + metadata (timestamp, SHA-256, bytes) vào `data/raw/`.

### `data_cleaner.py`
- **Class `DataCleaner`**: fluent builder pattern – mỗi bước trả về `self`.
- Các phương thức: `drop_duplicates()`, `clean_text()`, `to_datetime()`, `to_numeric()`, `fill_value()`, `fill_group_median()`.
- Mỗi bước ghi vào `report["steps"]` → xuất `cleaning_report.json`.
- **Hàm `clean_olist(raw)`**: recipe riêng cho từng bảng dưới dạng hàm độc lập.

### `data_validator.py`
- **Class `DataValidator`**: fluent chaining – `check_keys().check_foreign_keys()...`.
- 30 quy tắc chia làm 5 nhóm: PK, FK, DOM, DATE, MISS.
- `outliers_iqr()`: phân tích IQR cho `price`, `freight_value`, `payment_value`.
- Status: `PASS` / `WARN` (severity=warning) / `FAIL` (severity=error).

### `pipeline.py`
- `step_collect`, `step_read_olist`, `step_clean`, `step_validate`, `step_save` – mỗi bước là hàm độc lập, có thể test riêng.
- Exit code `1` khi có rule FAIL.
- Hỗ trợ xuất Parquet qua `pyarrow` (optional).

---

## Chiến lược thu thập dữ liệu

```
                 ┌──────────────────────┐
                 │  Wikipedia MediaWiki │  ← Ưu tiên 1 (không cần API key)
                 │  /w/api.php          │
                 └──────────┬───────────┘
                    Thất bại │
                 ┌──────────▼───────────┐
                 │  IBGE Localidades    │  ← Ưu tiên 2 (API chính thức Brazil)
                 │  /api/v1/localidades │
                 └──────────┬───────────┘
                    Thất bại │
                 ┌──────────▼───────────┐
                 │  Embedded Fallback   │  ← Ưu tiên 3 (dữ liệu tĩnh offline)
                 └──────────────────────┘
```

---

## Quy trình làm sạch

| Bước | Mô tả |
|---|---|
| Xóa trùng | `drop_duplicates()` toàn bộ → theo khóa chính |
| Chuẩn hóa text | Strip whitespace, áp lowercase/uppercase |
| Chuẩn hóa kiểu | `to_datetime` (coerce), `to_numeric` (coerce), `Int64` cho số nguyên nullable |
| Điền NULL | `fill_value` (chuỗi cố định), `fill_group_median` (median theo nhóm) |
| Gắn nhãn tiếng Anh | LEFT JOIN với `category_translation` + bổ sung 2 bản dịch thủ công |

---

## Báo cáo đầu ra

`cleaning_report.json` gồm 2 phần:

```jsonc
{
  "cleaning": {
    "<table_name>": {
      "rows_in": <int>,
      "rows_out": <int>,
      "steps": { ... },       // chi tiết từng bước
      "missing_after": { ... } // NULL còn lại sau khi làm sạch
    }
  },
  "validation": {
    "summary": { "PASS": 25, "WARN": 5, "FAIL": 0 },
    "rules": [ { "rule": "...", "status": "PASS/WARN/FAIL", ... } ],
    "outliers": { "order_item.price": { "q1": ..., "above_fence": ... } }
  }
}
```

---

## Đánh giá so với yêu cầu Tuần 7

| Tiêu chí | Trạng thái |
|---|---|
| Thu thập dữ liệu bổ sung từ API | ✅ Wikipedia + IBGE + fallback |
| Làm sạch 8 bảng Olist | ✅ 0 FAIL |
| Kiểm tra PK / FK | ✅ 14 rules PASS |
| Kiểm tra domain values | ✅ 9 rules (7 PASS, 2 WARN có lý giải) |
| Kiểm tra thứ tự thời gian | ✅ 4 rules (1 PASS, 3 WARN có lý giải) |
| Kiểm tra completeness | ✅ 2 rules PASS |
| Phân tích outlier | ✅ IQR cho price, freight, payment |
| Báo cáo JSON | ✅ `cleaning_report.json` |
| Logging | ✅ `crawl_logs.txt` |

---

*Generated by Olist Data Pipeline v2.0*
