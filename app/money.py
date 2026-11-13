from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def parse_euros(text):
    if text is None:
        return None
    raw = str(text).strip().replace(" ", "").replace("€", "").replace(",", ".")
    if raw == "":
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("montant") from exc
    if value < 0 or value > Decimal("500"):
        raise ValueError("montant")
    cents = (value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def format_eur(cents):
    if cents is None:
        return None
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return f"{sign}{cents // 100},{cents % 100:02d} \u20ac"
