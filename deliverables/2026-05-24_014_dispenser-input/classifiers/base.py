from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Classification:
    product_id: str          # key in pricing table — also the intent name
    product_label: str       # human-readable label shown to user / on receipt
    price_eur: float
    extras: dict = field(default_factory=dict)


class RequestClassifier(ABC):
    """Maps a user's request into a priced product entry from the catalog.

    v1: CatalogClassifier — user picks the product from a dropdown.
    v2: LLMClassifier — free-text request, LLM picks the closest product (or escalates).
    """

    @abstractmethod
    def classify(self, **kwargs) -> Classification: ...
