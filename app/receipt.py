import json
from datetime import datetime, timezone

from app.money import format_eur
from app.orders import METHOD_LABELS, PAY_LABELS, STATUS_LABELS, order_events
from app.schedule import PARIS

_MONTHS = (
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc.",
)

NIGHT = (0.110, 0.086, 0.071)
CREAM = (0.984, 0.973, 0.953)
PAPER = (0.965, 0.945, 0.910)
TERRACOTTA = (0.769, 0.318, 0.165)
SAFFRON = (0.784, 0.588, 0.180)
INK = (0.165, 0.110, 0.078)
SOFT = (0.369, 0.290, 0.235)
LINE = (0.890, 0.839, 0.769)
WHITE = (1, 1, 1)
HEADER_CREAM = (0.945, 0.910, 0.855)

_WIDTHS = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667, "'": 191,
    "(": 333, ")": 333, "*": 389, "+": 584, ",": 278, "-": 333, ".": 278, "/": 278,
    "0": 556, "1": 556, "2": 556, "3": 556, "4": 556, "5": 556, "6": 556, "7": 556, "8": 556, "9": 556,
    ":": 278, ";": 278, "<": 584, "=": 584, ">": 584, "?": 556,
    "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778, "H": 722, "I": 278,
    "J": 500, "K": 667, "L": 556, "M": 833, "N": 722, "O": 778, "P": 667, "Q": 778, "R": 722,
    "S": 667, "T": 611, "U": 722, "V": 667, "W": 944, "X": 667, "Y": 667, "Z": 611,
    "a": 556, "b": 556, "c": 500, "d": 556, "e": 556, "f": 278, "g": 556, "h": 556, "i": 222,
    "j": 222, "k": 500, "l": 222, "m": 833, "n": 556, "o": 556, "p": 556, "q": 556, "r": 333,
    "s": 500, "t": 278, "u": 556, "v": 500, "w": 722, "x": 500, "y": 500, "z": 500,
    "é": 556, "è": 556, "ê": 556, "ë": 556, "à": 556, "â": 556, "ä": 556, "ù": 556, "û": 556, "ü": 556,
    "ô": 556, "ö": 556, "î": 278, "ï": 278, "ç": 500, "É": 667, "È": 667, "À": 667, "Ç": 722,
    "€": 556, "–": 556, "—": 1000, "·": 278, "×": 584, "’": 191,
}


def _literal(text):
    data = str(text).encode("cp1252", errors="replace")
    pieces = []
    for byte in data:
        if byte in b"\\()":
            pieces.append(b"\\" + bytes([byte]))
        elif 32 <= byte <= 126:
            pieces.append(bytes([byte]))
        else:
            pieces.append(f"\\{byte:03o}".encode("ascii"))
    return b"(" + b"".join(pieces) + b")"


def _rgb(color):
    return f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f}"


def _text_width(text, size):
    return sum(_WIDTHS.get(char, 520) for char in str(text)) * size / 1000


def _wrap(text, size, max_width):
    words = str(text).split(" ")
    lines = []
    current = ""
    for word in words:
        piece = word
        while piece and _text_width(piece, size) > max_width and len(piece) > 1:
            cut = 1
            while cut < len(piece) and _text_width(piece[: cut + 1], size) <= max_width:
                cut += 1
            lines.append(piece[:cut])
            piece = piece[cut:]
        trial = piece if not current else f"{current} {piece}"
        if current and _text_width(trial, size) > max_width:
            lines.append(current)
            current = piece
        else:
            current = trial
    if current or not lines:
        lines.append(current)
    return lines


def _assemble(pages):
    font_regular = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    font_bold = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    content_ids = []
    page_ids = []
    next_id = 5
    for _page in pages:
        content_ids.append(next_id)
        next_id += 1
        page_ids.append(next_id)
        next_id += 1
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: font_regular,
        4: font_bold,
        2: f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(f'{pid} 0 R' for pid in page_ids)}] >>".encode(),
    }
    for content, content_id, page_id in zip(pages, content_ids, page_ids):
        objects[content_id] = b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        ).encode()
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    last = next_id - 1
    for number in range(1, last + 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode()
        out += objects[number]
        out += b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {last + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for number in range(1, last + 1):
        out += f"{offsets[number]:010d} 00000 n \n".encode()
    out += f"trailer << /Size {last + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


class _Sheet:
    def __init__(self, ref):
        self.ref = ref
        self.pages = []
        self.ops = []
        self.y = 734

    def rect(self, x, y, w, h, color):
        self.ops.append(f"{_rgb(color)} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f".encode())

    def hline(self, x, y, w, color, weight=0.6):
        self.ops.append(f"{weight:.2f} w {_rgb(color)} RG {x:.2f} {y:.2f} m {x + w:.2f} {y:.2f} l S".encode())

    def text_at(self, x, y, value, size=10, bold=False, color=INK, align="left"):
        text = str(value)
        if align == "right":
            x -= _text_width(text, size)
        elif align == "center":
            x -= _text_width(text, size) / 2
        font = b"F2" if bold else b"F1"
        self.ops.append(
            f"{_rgb(color)} rg BT /".encode()
            + font
            + f" {size} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ".encode()
            + _literal(text)
            + b" Tj ET"
        )

    def _footer(self):
        self.hline(40, 40, 515, LINE, 0.6)
        self.text_at(40, 24, "ALLOKODRONE  ·  24 rue Emmanuel Arago, 93130 Noisy-le-Sec", 8, color=SOFT)
        self.text_at(555, 24, self.ref, 8, color=SOFT, align="right")

    def _hero(self, when):
        self.rect(0, 748, 595, 94, NIGHT)
        self.rect(0, 742, 595, 6, TERRACOTTA)
        self.text_at(40, 804, "ALLOKODRONE", 16, bold=True, color=WHITE)
        self.text_at(40, 786, "L'Afrique servie à grande vitesse.", 9, color=SAFFRON)
        self.text_at(40, 770, "24 rue Emmanuel Arago, 93130 Noisy-le-Sec", 8, color=HEADER_CREAM)
        self.text_at(555, 808, "COMMANDE", 8, bold=True, color=SAFFRON, align="right")
        self.text_at(555, 788, self.ref, 13, bold=True, color=WHITE, align="right")
        self.text_at(555, 770, when, 8, color=HEADER_CREAM, align="right")

    def _mini_header(self):
        self.rect(0, 800, 595, 42, NIGHT)
        self.rect(0, 796, 595, 4, TERRACOTTA)
        self.text_at(40, 816, "ALLOKODRONE", 11, bold=True, color=WHITE)
        self.text_at(555, 816, self.ref, 11, bold=True, color=WHITE, align="right")

    def new_page(self, continued=False, when=""):
        if self.ops:
            self.pages.append(b"\n".join(self.ops))
        self.ops = []
        self.rect(0, 0, 595, 842, CREAM)
        if continued:
            self._mini_header()
            self.y = 776
        else:
            self._hero(when)
            self.y = 718
        self._footer()

    def need(self, height):
        if self.y - height < 58:
            self.new_page(True)

    def gap(self, amount):
        self.y -= amount

    def heading(self, label):
        self.need(28)
        self.text_at(40, self.y, label, 8, bold=True, color=TERRACOTTA)
        self.y -= 16

    def finish(self):
        if self.ops or not self.pages:
            self.pages.append(b"\n".join(self.ops))
        return _assemble(self.pages)


def _when(value):
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return value or ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(PARIS)
    return f"{local.day} {_MONTHS[local.month - 1]} {local.year}  ·  {local.strftime('%H:%M')}"


def _day(value):
    parts = str(value).split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return str(value)
    year, month, day = (int(part) for part in parts)
    if month < 1 or month > 12:
        return str(value)
    return f"{day} {_MONTHS[month - 1]} {year}"


def _money(cents):
    label = format_eur(cents)
    return label if label else ""


def _address(order):
    if order["mode"] != "delivery" or not order["address_json"]:
        return ""
    try:
        data = json.loads(order["address_json"])
    except (TypeError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    city = f"{data.get('code_postal', '')} {data.get('ville', '')}".strip()
    return ", ".join(part for part in (data.get("rue"), city) if part)


def _card_height(lines, inner):
    count = 0
    for line in lines:
        count += len(_wrap(line, 10, inner))
    return 40 + count * 14


def _paint_card(sheet, x, top, w, title, lines, height):
    inner = w - 28
    wrapped = []
    for line in lines:
        wrapped.extend(_wrap(line, 10, inner))
    bottom = top - height
    sheet.rect(x, bottom, w, height, PAPER)
    sheet.rect(x, top - 3, w, 3, TERRACOTTA)
    sheet.text_at(x + 14, top - 18, title, 8, bold=True, color=TERRACOTTA)
    baseline = top - 36
    for line in wrapped:
        sheet.text_at(x + 14, baseline, line, 10, color=INK)
        baseline -= 14
    return bottom


def _table_head(sheet):
    sheet.need(36)
    top = sheet.y
    sheet.rect(40, top - 18, 515, 22, NIGHT)
    sheet.text_at(52, top - 12, "Article", 8, bold=True, color=WHITE)
    sheet.text_at(438, top - 12, "Qté", 8, bold=True, color=WHITE, align="right")
    sheet.text_at(543, top - 12, "Montant", 8, bold=True, color=WHITE, align="right")
    sheet.y = top - 32


def _paint_line(sheet, line):
    name = line.get("name") or "Article"
    quantity = str(line.get("quantity") or 0)
    amount = _money(line.get("line_cents"))
    names = _wrap(name, 10, 330)
    extra = []
    options = (line.get("options") or "").strip()
    notes = (line.get("notes") or "").strip()
    if options:
        extra.extend(_wrap(options, 8, 330))
    if notes:
        extra.extend(_wrap(f"Instruction : {notes}", 8, 330))
    height = 12 + len(names) * 13 + len(extra) * 11
    if sheet.y - height < 58:
        sheet.new_page(True)
        _table_head(sheet)
    baseline = sheet.y
    for index, text in enumerate(names):
        sheet.text_at(52, baseline, text, 10, bold=index == 0, color=INK)
        if index == 0:
            sheet.text_at(438, baseline, quantity, 10, color=INK, align="right")
            sheet.text_at(543, baseline, amount, 10, color=INK, align="right")
        baseline -= 13
    for text in extra:
        sheet.text_at(52, baseline, text, 8, color=SOFT)
        baseline -= 11
    sheet.y = baseline - 4
    sheet.hline(40, sheet.y, 515, LINE, 0.4)
    sheet.y -= 12


def render_order_pdf(conn, order):
    slot = None
    if order["slot_id"]:
        slot = conn.execute("SELECT * FROM pickup_slots WHERE id = ?", (order["slot_id"],)).fetchone()
    point = None
    if order["pickup_point_id"]:
        point = conn.execute("SELECT * FROM pickup_points WHERE id = ?", (order["pickup_point_id"],)).fetchone()
    zone = None
    if order["zone_id"]:
        zone = conn.execute("SELECT * FROM delivery_zones WHERE id = ?", (order["zone_id"],)).fetchone()
    method_row = conn.execute(
        "SELECT label FROM payment_methods WHERE code = ?",
        (order["payment_method"],),
    ).fetchone()
    method = ""
    if method_row and method_row["label"]:
        method = method_row["label"]
    elif order["payment_method"] in METHOD_LABELS:
        method = METHOD_LABELS[order["payment_method"]]
    try:
        lines = json.loads(order["snapshot_json"])
    except (TypeError, json.JSONDecodeError):
        lines = []
    if not isinstance(lines, list):
        lines = []

    client = [order["customer_name"]]
    if order["email"]:
        client.append(order["email"])
    if order["phone"]:
        client.append(order["phone"])
    service = []
    if order["mode"] == "pickup":
        service.append("Click & Collect")
    elif order["mode"] == "delivery":
        service.append("Livraison")
    elif order["mode"]:
        service.append(order["mode"])
    if point:
        service.append(point["name"])
        if point["address"]:
            service.append(point["address"])
    if slot:
        service.append(f"{_day(slot['slot_date'])}  ·  {slot['start_time']} – {slot['end_time']}")
    address = _address(order)
    if address:
        service.append(address)
    if zone and zone["name"]:
        service.append(f"Zone {zone['name']}")
    if method:
        service.append(method)
    pay = PAY_LABELS.get(order["payment_status"])
    if pay:
        service.append(f"Paiement {pay.lower()}")

    sheet = _Sheet(order["public_ref"])
    sheet.new_page(when=_when(order["created_at"]))
    status = STATUS_LABELS.get(order["status"], order["status"])
    chip = _text_width(status, 9) + 18
    sheet.need(28)
    sheet.rect(40, sheet.y - 14, chip, 18, TERRACOTTA)
    sheet.text_at(49, sheet.y - 9, status, 9, bold=True, color=WHITE)
    sheet.y -= 36

    left_h = _card_height(client, 220)
    right_h = _card_height(service, 220) if service else 0
    shared = max(left_h, right_h)
    sheet.need(shared + 8)
    top = sheet.y
    left_bottom = _paint_card(sheet, 40, top, 248, "CLIENT", client, shared if service else left_h)
    right_bottom = top
    if service:
        right_bottom = _paint_card(sheet, 307, top, 248, "SERVICE", service, shared)
    sheet.y = min(left_bottom, right_bottom) - 28

    sheet.heading("REÇU")
    _table_head(sheet)
    for line in lines:
        if isinstance(line, dict):
            _paint_line(sheet, line)
    sheet.gap(6)

    totals = [
        ("Sous-total", _money(order["subtotal_cents"])),
        ("Livraison", _money(order["delivery_fee_cents"])),
        ("Réduction", _money(order["discount_cents"])),
    ]
    if order["promo_code"]:
        totals.append(("Code", order["promo_code"]))
    box_h = 22 + len(totals) * 16 + 26
    sheet.need(box_h + 8)
    box_x = 325
    box_w = 230
    box_top = sheet.y
    box_bottom = box_top - box_h
    sheet.rect(box_x, box_bottom, box_w, box_h, PAPER)
    baseline = box_top - 18
    for label, value in totals:
        sheet.text_at(box_x + 14, baseline, label, 9, color=SOFT)
        sheet.text_at(543, baseline, value, 9, color=INK, align="right")
        baseline -= 16
    sheet.hline(box_x + 14, baseline + 8, box_w - 26, TERRACOTTA, 1)
    sheet.text_at(box_x + 14, baseline - 10, "Total", 12, bold=True, color=INK)
    sheet.text_at(543, baseline - 10, _money(order["total_cents"]), 12, bold=True, color=TERRACOTTA, align="right")
    sheet.y = box_bottom - 28

    events = list(order_events(conn, order["id"]))
    if events:
        sheet.heading("SUIVI")
        for event in events:
            label = STATUS_LABELS.get(event["status"], event["status"])
            sheet.need(18)
            sheet.rect(40, sheet.y + 1, 5, 5, SAFFRON)
            sheet.text_at(54, sheet.y, label, 10, color=INK)
            sheet.text_at(543, sheet.y, _when(event["created_at"]), 9, color=SOFT, align="right")
            sheet.y -= 16
    return sheet.finish()
