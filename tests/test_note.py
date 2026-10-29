"""The research note: three to five pages, no long dash, and the featured figures the site shows."""

import json
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "Voyage-Economics-TCE-Research-Note.pdf"


def _note() -> tuple[int, str]:
    with pdfplumber.open(NOTE) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return len(pdf.pages), " ".join(text.split())


def test_the_note_is_three_to_five_pages_with_no_long_dash():
    pages, text = _note()
    assert 3 <= pages <= 5
    assert chr(0x2014) not in text
    assert chr(0x2013) not in text


def test_the_note_prints_the_overview_figures_of_the_site():
    _, text = _note()
    overview = json.loads((ROOT / "data" / "overview.json").read_text(encoding="utf-8"))
    facts = {fact["id"]: fact["value"]["value"] for fact in overview["facts"]}
    assert "USD {:,.0f} a day".format(facts["tce"]) in text
    assert "USD {:,.2f} a tonne".format(facts["breakeven"]) in text
