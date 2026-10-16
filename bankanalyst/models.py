from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class Transaction:
    bank: str
    booking_date: date
    value_date: date | None
    description: str
    amount: Decimal  # negative = uscita, positive = entrata
    source: str
    page: int
    sign_uncertain: bool = False  # sign guessed from the wording, not from a Dare/Avere column
    category: str = ""


@dataclass
class Statement:
    path: str
    bank: str
    transactions: list[Transaction] = field(default_factory=list)
    opening: Decimal | None = None
    closing: Decimal | None = None
    warnings: list[str] = field(default_factory=list)

    def reconciliation(self) -> str:
        """'ok' when saldo iniziale + movimenti = saldo finale, 'diff …' otherwise, 'n.d.' without both balances."""
        if self.opening is None or self.closing is None:
            return "n.d."
        diff = self.opening + sum((t.amount for t in self.transactions), Decimal("0")) - self.closing
        return "ok" if abs(diff) < Decimal("0.01") else f"diff {diff:+.2f}"
