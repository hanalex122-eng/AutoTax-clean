from parser.vendor_detector import detect_vendor
from parser.heuristics import parse_total
from parser.vat import parse_vat_rate
from parser.date import parse_date
from parser.confidence_engine import score_invoice


def parse_invoice(text):

    data = {}

    data["vendor"] = detect_vendor(text)

    data["date"] = parse_date(text)

    data["total"] = parse_total(text)

    data["vat_rate"] = parse_vat_rate(text)

    score = score_invoice(data)

    if score < 60:

        data["status"] = "review"

    else:

        data["status"] = "ok"

    return data