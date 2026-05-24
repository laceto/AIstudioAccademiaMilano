import json
from pathlib import Path

from .base import Classification, RequestClassifier

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SETTINGS = PROJECT_ROOT / "config" / "global_settings.json"

PRODUCT_LABELS = {
    "static_landing_page": "Static landing page",
    "pdf_document": "PDF document",
    "invoice_pdf": "Invoice PDF",
    "strategic_report": "Strategic report",
    "chatbot_app": "Streamlit chatbot",
    "email_delivery": "Email delivery add-on",
    "rag_knowledge_base": "RAG knowledge base",
    "calendar_integration": "Calendar integration",
    "weather_dashboard": "Weather dashboard",
    "agent_deploy_streamlit": "Agent deploy (Streamlit)",
}


def _parse_price(raw) -> float | None:
    if raw is None:
        return None
    return float(str(raw).replace("€", "").replace(",", ".").strip())


class CatalogClassifier(RequestClassifier):
    def __init__(self, settings_path: Path | str = DEFAULT_SETTINGS) -> None:
        self.settings_path = Path(settings_path)
        with self.settings_path.open() as f:
            self.pricing: dict = json.load(f)["pricing"]

    def list_products(self) -> list[dict]:
        products = []
        for pid, raw in self.pricing.items():
            price = _parse_price(raw)
            if pid == "unknown_product" or price is None:
                continue
            products.append({
                "id": pid,
                "label": PRODUCT_LABELS.get(pid, pid.replace("_", " ").title()),
                "price_eur": price,
            })
        return sorted(products, key=lambda p: p["price_eur"])

    def classify(self, product_id: str, free_text: str = "", **extras) -> Classification:
        price = _parse_price(self.pricing.get(product_id))
        if price is None:
            raise ValueError(
                f"Unknown or blocked product: {product_id!r}. "
                "Marco's `unknown_product: null` rule applies — escalate to Luigi."
            )
        return Classification(
            product_id=product_id,
            product_label=PRODUCT_LABELS.get(product_id, product_id),
            price_eur=price,
            extras={"free_text": free_text, **extras},
        )
