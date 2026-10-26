"""config.py - Cấu hình tập trung cho Olist Data Pipeline.

Mọi hằng số (tên file, khóa chính, domain values, URL API) đều nằm ở đây
để các module khác không hard-code, dễ bảo trì và mở rộng.
"""

# ── Ánh xạ tên file Kaggle → tên bảng nội bộ ─────────────────────────────────
FILES: dict[str, str] = {
    "olist_customers_dataset.csv":            "customer",
    "olist_sellers_dataset.csv":              "seller",
    "product_category_name_translation.csv":  "category_translation",
    "olist_products_dataset.csv":             "product",
    "olist_orders_dataset.csv":               "orders",
    "olist_order_items_dataset.csv":          "order_item",
    "olist_order_payments_dataset.csv":       "order_payment",
    "olist_order_reviews_dataset.csv":        "order_review",
}

# ── Khóa chính của từng bảng ──────────────────────────────────────────────────
KEYS: dict[str, list[str]] = {
    "customer":            ["customer_id"],
    "seller":              ["seller_id"],
    "category_translation":["product_category_name"],
    "product":             ["product_id"],
    "orders":              ["order_id"],
    "order_item":          ["order_id", "order_item_id"],
    "order_payment":       ["order_id", "payment_sequential"],
    "order_review":        ["review_id", "order_id"],
}

# ── Domain values ─────────────────────────────────────────────────────────────
ORDER_STATUS: set[str] = {
    "delivered", "shipped", "canceled", "unavailable",
    "invoiced", "processing", "created", "approved",
}

PAYMENT_TYPES: set[str] = {
    "credit_card", "boleto", "voucher", "debit_card", "not_defined",
}

# ── Bản dịch thủ công cho 2 danh mục Kaggle chưa có trong file translation ────
MANUAL_TRANSLATION: dict[str, str] = {
    "pc_gamer":                                    "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_and_food_preparers",
}

# ── API Endpoints ─────────────────────────────────────────────────────────────
IBGE_STATES_URL:   str = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
WIKIPEDIA_API_URL: str = "https://en.wikipedia.org/w/api.php"

# ── Bản đồ vùng Brazil (state_code → (region_code, region_name)) ─────────────
STATE_REGION: dict[str, tuple[str, str]] = {
    "AC": ("N",  "Norte"),       "AP": ("N",  "Norte"),
    "AM": ("N",  "Norte"),       "PA": ("N",  "Norte"),
    "RO": ("N",  "Norte"),       "RR": ("N",  "Norte"),
    "TO": ("N",  "Norte"),
    "AL": ("NE", "Nordeste"),    "BA": ("NE", "Nordeste"),
    "CE": ("NE", "Nordeste"),    "MA": ("NE", "Nordeste"),
    "PB": ("NE", "Nordeste"),    "PE": ("NE", "Nordeste"),
    "PI": ("NE", "Nordeste"),    "RN": ("NE", "Nordeste"),
    "SE": ("NE", "Nordeste"),
    "DF": ("CO", "Centro-Oeste"),"GO": ("CO", "Centro-Oeste"),
    "MS": ("CO", "Centro-Oeste"),"MT": ("CO", "Centro-Oeste"),
    "ES": ("SE", "Sudeste"),     "MG": ("SE", "Sudeste"),
    "RJ": ("SE", "Sudeste"),     "SP": ("SE", "Sudeste"),
    "PR": ("S",  "Sul"),         "RS": ("S",  "Sul"),
    "SC": ("S",  "Sul"),
}

# ── Dữ liệu bang nhúng sẵn (offline fallback) ────────────────────────────────
IBGE_STATES_FALLBACK: list[dict] = [
    # Norte
    {"state_id": 12, "state_code": "AC", "state_name": "Acre",
     "region_id": 1, "region_code": "N",  "region_name": "Norte"},
    {"state_id": 16, "state_code": "AP", "state_name": "Amapá",
     "region_id": 1, "region_code": "N",  "region_name": "Norte"},
    {"state_id": 13, "state_code": "AM", "state_name": "Amazonas",
     "region_id": 1, "region_code": "N",  "region_name": "Norte"},
    {"state_id": 15, "state_code": "PA", "state_name": "Pará",
     "region_id": 1, "region_code": "N",  "region_name": "Norte"},
    {"state_id": 11, "state_code": "RO", "state_name": "Rondônia",
     "region_id": 1, "region_code": "N",  "region_name": "Norte"},
    {"state_id": 14, "state_code": "RR", "state_name": "Roraima",
     "region_id": 1, "region_code": "N",  "region_name": "Norte"},
    {"state_id": 17, "state_code": "TO", "state_name": "Tocantins",
     "region_id": 1, "region_code": "N",  "region_name": "Norte"},
    # Nordeste
    {"state_id": 27, "state_code": "AL", "state_name": "Alagoas",
     "region_id": 2, "region_code": "NE", "region_name": "Nordeste"},
    {"state_id": 29, "state_code": "BA", "state_name": "Bahia",
     "region_id": 2, "region_code": "NE", "region_name": "Nordeste"},
    {"state_id": 23, "state_code": "CE", "state_name": "Ceará",
     "region_id": 2, "region_code": "NE", "region_name": "Nordeste"},
    {"state_id": 21, "state_code": "MA", "state_name": "Maranhão",
     "region_id": 2, "region_code": "NE", "region_name": "Nordeste"},
    {"state_id": 25, "state_code": "PB", "state_name": "Paraíba",
     "region_id": 2, "region_code": "NE", "region_name": "Nordeste"},
    {"state_id": 26, "state_code": "PE", "state_name": "Pernambuco",
     "region_id": 2, "region_code": "NE", "region_name": "Nordeste"},
    {"state_id": 22, "state_code": "PI", "state_name": "Piauí",
     "region_id": 2, "region_code": "NE", "region_name": "Nordeste"},
    {"state_id": 24, "state_code": "RN", "state_name": "Rio Grande do Norte",
     "region_id": 2, "region_code": "NE", "region_name": "Nordeste"},
    {"state_id": 28, "state_code": "SE", "state_name": "Sergipe",
     "region_id": 2, "region_code": "NE", "region_name": "Nordeste"},
    # Centro-Oeste
    {"state_id": 53, "state_code": "DF", "state_name": "Distrito Federal",
     "region_id": 5, "region_code": "CO", "region_name": "Centro-Oeste"},
    {"state_id": 52, "state_code": "GO", "state_name": "Goiás",
     "region_id": 5, "region_code": "CO", "region_name": "Centro-Oeste"},
    {"state_id": 50, "state_code": "MS", "state_name": "Mato Grosso do Sul",
     "region_id": 5, "region_code": "CO", "region_name": "Centro-Oeste"},
    {"state_id": 51, "state_code": "MT", "state_name": "Mato Grosso",
     "region_id": 5, "region_code": "CO", "region_name": "Centro-Oeste"},
    # Sudeste
    {"state_id": 32, "state_code": "ES", "state_name": "Espírito Santo",
     "region_id": 3, "region_code": "SE", "region_name": "Sudeste"},
    {"state_id": 31, "state_code": "MG", "state_name": "Minas Gerais",
     "region_id": 3, "region_code": "SE", "region_name": "Sudeste"},
    {"state_id": 33, "state_code": "RJ", "state_name": "Rio de Janeiro",
     "region_id": 3, "region_code": "SE", "region_name": "Sudeste"},
    {"state_id": 35, "state_code": "SP", "state_name": "São Paulo",
     "region_id": 3, "region_code": "SE", "region_name": "Sudeste"},
    # Sul
    {"state_id": 41, "state_code": "PR", "state_name": "Paraná",
     "region_id": 4, "region_code": "S",  "region_name": "Sul"},
    {"state_id": 43, "state_code": "RS", "state_name": "Rio Grande do Sul",
     "region_id": 4, "region_code": "S",  "region_name": "Sul"},
    {"state_id": 42, "state_code": "SC", "state_name": "Santa Catarina",
     "region_id": 4, "region_code": "S",  "region_name": "Sul"},
]
