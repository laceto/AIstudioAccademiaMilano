from .base import Classification, RequestClassifier


class LLMClassifier(RequestClassifier):
    """Free-text → priced product classifier — v2 stub.

    Planned implementation:
      1. Load the priced catalog from config/global_settings.json
      2. Prompt an LLM (OpenAI or Anthropic) with:
           - The free-text request
           - The catalog (product_id + label + price + 1-line description)
           - Required fields per product type (from process/intent_registry.yaml)
      3. LLM returns structured output (Pydantic):
           {product_id: str, confidence: float, missing_fields: list[str], rationale: str}
      4. Decision logic:
           - confidence ≥ 0.8 AND product_id in catalog AND no missing_fields → return Classification
           - confidence < 0.8 OR product_id not in catalog → Marco escalation
             (notify Luigi via Telegram, do NOT take payment)
           - missing_fields present → return Classification with a `needs_followup` flag
             so the form can ask for the missing inputs before payment

    Cost target: <€0.001 per classification using gpt-4o-mini or claude-haiku.
    """

    def classify(self, free_text: str, **_) -> Classification:
        raise NotImplementedError(
            "LLMClassifier planned for v2 — see docstring for the implementation contract."
        )
