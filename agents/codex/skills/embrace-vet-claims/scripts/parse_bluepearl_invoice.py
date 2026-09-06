#!/usr/bin/env python3
from decimal import Decimal
import json
from pathlib import Path
import re
import sys


def money(value: str | None) -> str | None:
    if value is None:
        return None
    return str(Decimal(value.replace(",", "")))


def first_match(pattern: str, text: str, flags: int = 0) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else None


def parse_invoice(text: str) -> dict[str, str | None]:
    invoice_number = first_match(r"Invoice\s+#:\s*(\d+)", text)
    invoice_date = first_match(r"Date:\s*(\d{1,2}/\d{1,2}/\d{4})", text)
    patient = first_match(r"Patient Name:\s*([A-Za-z][A-Za-z '-]+?)\s+Breed:", text)

    totals = re.findall(r"(?m)^Total:\s*\$([\d,]+\.\d{2})\s*$", text)
    balances_due = re.findall(r"Balance Due:\s*\$([\d,]+\.\d{2})", text)
    paid = first_match(r"Credit-[^:]+:\s*\(\$([\d,]+\.\d{2})\)", text)

    total = money(totals[-1]) if totals else None
    balance_due = money(balances_due[-1]) if balances_due else None
    amount_paid = money(paid)

    if total == "0.00":
        claim_action = "archive_zero_invoice"
    elif total:
        claim_action = "submit"
    else:
        claim_action = "review"

    return {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "patient": patient,
        "total": total,
        "balance_due": balance_due,
        "amount_paid": amount_paid,
        "claim_action": claim_action,
    }


def read_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError as exc:
        raise SystemExit(
            "pdfplumber is required to parse BluePearl invoice PDFs"
        ) from exc

    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: parse_bluepearl_invoice.py <invoice.pdf>")

    path = Path(sys.argv[1]).expanduser()
    text = read_pdf(path)
    result = parse_invoice(text)
    result["path"] = str(path)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
