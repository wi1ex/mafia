from __future__ import annotations
from decimal import Decimal, InvalidOperation
import re

DC_PACKAGE_QUANTITIES = (25, 50, 100, 250)
DC_CURRENCIES = ("RUB", "USD", "EUR")
DEFAULT_DC_PACKAGES = "475-6.20-5.50-800-10.60-9.40-1500-20-17.60-3500-46.60-41.20"
DC_PRICE_QUANTUM = Decimal("0.01")
MAX_DC_PRICE = Decimal("9999999999999999.99")
DC_PACKAGE_PRICE_RE = re.compile(r"[0-9]+(?:[.,][0-9]{1,2})?", flags=re.ASCII)


def normalize_dc_price(value: object, currency: str = "RUB") -> Decimal:
    currency = str(currency).upper()
    if currency not in DC_CURRENCIES:
        raise ValueError("dc_currency_invalid")

    if isinstance(value, bool):
        raise ValueError("dc_price_invalid")

    try:
        price = Decimal(str(value).strip())
        if not price.is_finite() or price <= 0 or price > MAX_DC_PRICE:
            raise ValueError("dc_price_invalid")

        normalized = price.quantize(DC_PRICE_QUANTUM)
        if normalized != price:
            raise ValueError("dc_price_invalid")

        return normalized

    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("dc_price_invalid") from exc


def dc_price_text(value: object, currency: str = "RUB") -> str:
    return format(normalize_dc_price(value, currency), ".2f")


def normalize_dc_packages(value: object) -> str:
    if value is None:
        value = DEFAULT_DC_PACKAGES
    if not isinstance(value, str):
        raise ValueError("dc_packages_invalid")

    tokens = value.split("-")
    if len(tokens) != len(DC_PACKAGE_QUANTITIES) * len(DC_CURRENCIES):
        raise ValueError("dc_packages_invalid")

    normalized: list[str] = []
    for token in tokens:
        token = token.strip()
        if not DC_PACKAGE_PRICE_RE.fullmatch(token):
            raise ValueError("dc_packages_invalid")

        price = dc_price_text(token.replace(",", "."))
        normalized.append(price[:-3] if price.endswith(".00") else price)
    return "-".join(normalized)


def parse_dc_packages(value: object) -> dict[str, dict[str, str]]:
    prices = normalize_dc_packages(value).split("-")
    return {
        str(quantity): {
            currency: format(Decimal(prices[index * len(DC_CURRENCIES) + offset]), ".2f")
            for offset, currency in enumerate(DC_CURRENCIES)
        }
        for index, quantity in enumerate(DC_PACKAGE_QUANTITIES)
    }
