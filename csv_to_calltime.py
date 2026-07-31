#!/usr/bin/env python3
"""
csv_to_calltime.py — Convert an arbitrary donor-data CSV into an .xlsx file
formatted for Call Time's "Import CSV or Excel" feature.

Usage:
    python csv_to_calltime.py input.csv
    python csv_to_calltime.py input.csv -o output.xlsx

What Call Time's import actually expects (read straight from index.html's
csvFileInput handler — see the comment block below for the source):
  - Header row matching is CASE-INSENSITIVE SUBSTRING matching, not exact
    match, and COLUMN ORDER DOES NOT MATTER. e.g. a header of "Phone Number"
    matches because it contains "phone".
  - The only required column is Name — if no header contains "name", the
    app refuses the whole file. Per-row, any row with a blank name is
    silently skipped (no error shown), so we flag those before you upload.
  - Every field is stored as free text; there is no date column and no
    strict phone format enforced by the app. "Last Gift" is one combined
    free-text field, e.g. "$100, March 2026" (not separate amount/date
    columns).
  - Category text just needs to CONTAIN one of these words (case-insensitive):
      "follow"            -> Needs Follow Up
      "current"           -> Current
      "complete" (no "not")-> Complete
      "not" (or blank)    -> Not Complete
    Anything else defaults to Not Complete.

This script writes clean, canonical headers ("Name", "Phone", "Email",
"Address", "City", "Organization", "Occupation", "Ask", "Last Gift", "Notes",
"Category") so they match the app's substring rules unambiguously, and
tries hard to map whatever your source CSV actually calls those columns
(including combining separate First/Last Name columns, or separate
street/city/state/zip columns, or separate gift-amount/gift-date columns).
A separate City column is only filled in when the source CSV has its own
city field -- the app otherwise guesses city from Address text, which is
less reliable, so a real city source column is always preferred here.

Requires: pandas, openpyxl  (pip install pandas openpyxl)
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Column aliases: canonical Call Time field -> patterns to look for in a
# source header (checked as case-insensitive substrings, longest/most
# specific first so e.g. "last gift date" doesn't get grabbed by a bare
# "last" check meant for a generic "last gift" column).
# ---------------------------------------------------------------------------
FIELD_ALIASES = {
    "name": ["full name", "donor name", "contact name", "name"],
    "first_name": ["first name", "firstname", "fname", "given name"],
    "last_name": ["last name", "lastname", "lname", "surname", "family name"],
    "phone": ["mobile phone", "cell phone", "home phone", "work phone",
              "telephone", "mobile", "cell", "phone"],
    "email": ["email address", "e-mail", "email"],
    "address": ["mailing address", "home address", "street address",
                "full address", "address"],
    "street": ["street", "address line 1", "address1", "addr1"],
    "city": ["city", "town"],
    "state": ["state", "province", "st"],
    "zip": ["zip code", "zipcode", "postal code", "zip"],
    "organization": ["employer", "company", "organization", "org"],
    "occupation": ["job title", "occupation", "profession", "title"],
    "ask": ["suggested ask", "ask amount", "ask"],
    "last_gift_combined": ["last gift"],
    "last_gift_amount": ["last gift amount", "most recent gift amount",
                          "gift amount", "donation amount"],
    "last_gift_date": ["last gift date", "most recent gift date",
                        "gift date", "donation date"],
    "notes": ["comments", "notes", "note"],
    "category": ["call status", "status", "category"],
}

# Resolution order matters: more specific fields must claim their column
# before broader/generic fields go looking, otherwise e.g. "First Name"
# gets swallowed by the generic "name" alias, or "Email Address" gets
# swallowed by the generic "address" alias. Once a column is claimed by an
# earlier (more specific) field, later fields skip it.
DIRECT_FIELDS = [
    "first_name", "last_name", "email", "street", "city", "state", "zip",
    "last_gift_amount", "last_gift_date", "phone", "organization",
    "occupation", "ask", "notes", "category",
    "name", "address", "last_gift_combined",
]

OUTPUT_COLUMNS = [
    "Name", "Phone", "Email", "Address", "City", "Organization", "Occupation",
    "Ask", "Last Gift", "Notes", "Category", "Review Notes",
]


def normalize_header(h):
    return re.sub(r"\s+", " ", str(h)).strip().lower()


def resolve_columns(columns):
    """Map canonical field name -> actual source column name (or None).

    Processes DIRECT_FIELDS in order (specific fields first); once a source
    column is claimed by a field it's excluded from matching later, broader
    fields, so e.g. "First Name" can't also get grabbed by the generic
    "name" alias.
    """
    normalized = {normalize_header(c): c for c in columns}
    claimed = set()
    resolved = {}
    for field in DIRECT_FIELDS:
        found = None
        # Exact match first.
        for alias in FIELD_ALIASES[field]:
            candidate = normalized.get(alias)
            if candidate and candidate not in claimed:
                found = candidate
                break
        # Substring match.
        if not found:
            for alias in FIELD_ALIASES[field]:
                for norm_header, original in normalized.items():
                    if original in claimed:
                        continue
                    if alias in norm_header:
                        found = original
                        break
                if found:
                    break
        resolved[field] = found
        if found:
            claimed.add(found)
    return resolved


def clean_phone(raw):
    if not raw or not str(raw).strip():
        return "", None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}", None
    # Doesn't look like a standard 10-digit US number — keep original text
    # as-is rather than mangling something like an international number.
    return str(raw).strip(), f"Unrecognized phone format: '{raw}'"


def clean_money(raw):
    if raw is None or str(raw).strip() == "":
        return ""
    s = str(raw).strip()
    negative = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return str(raw).strip()
    try:
        amount = float(s)
    except ValueError:
        return str(raw).strip()
    formatted = f"${amount:,.0f}" if amount == int(amount) else f"${amount:,.2f}"
    return f"-{formatted}" if negative else formatted


def clean_date(raw):
    if raw is None or str(raw).strip() == "":
        return ""
    parsed = pd.to_datetime(raw, errors="coerce")
    if pd.isna(parsed):
        return str(raw).strip()
    return parsed.strftime("%B %Y")


def normalize_category(raw):
    s = (raw or "").strip().lower()
    if not s:
        return ""
    if "follow" in s:
        return "Needs Follow Up"
    if "current" in s:
        return "Current"
    if "complete" in s and "not" not in s:
        return "Complete"
    if "not" in s:
        return "Not Complete"
    return None  # unrecognized — flagged, left blank (app defaults to Not Complete)


def build_address(row, cols):
    if cols["address"]:
        return str(row[cols["address"]]).strip()
    parts = []
    for key in ("street", "city", "state", "zip"):
        if cols[key] and str(row[cols[key]]).strip():
            parts.append(str(row[cols[key]]).strip())
    if not parts:
        return ""
    # "street, city, state zip" style.
    if cols["street"] and cols["city"]:
        street = str(row[cols["street"]]).strip() if cols["street"] else ""
        city = str(row[cols["city"]]).strip() if cols["city"] else ""
        state = str(row[cols["state"]]).strip() if cols["state"] else ""
        zip_ = str(row[cols["zip"]]).strip() if cols["zip"] else ""
        tail = " ".join(p for p in (state, zip_) if p)
        return ", ".join(p for p in (street, city, tail) if p)
    return ", ".join(parts)


def build_city(row, cols):
    # Only trust a source column that's actually a separate City field --
    # if all we have is one combined Address column, there's no reliable
    # city to pull out of it here (the app guesses from Address as a
    # fallback for rows like this).
    return str(row[cols["city"]]).strip() if cols["city"] else ""


def build_name(row, cols):
    if cols["name"] and str(row[cols["name"]]).strip():
        return str(row[cols["name"]]).strip()
    first = str(row[cols["first_name"]]).strip() if cols["first_name"] else ""
    last = str(row[cols["last_name"]]).strip() if cols["last_name"] else ""
    return " ".join(p for p in (first, last) if p)


def build_last_gift(row, cols):
    if cols["last_gift_combined"]:
        return str(row[cols["last_gift_combined"]]).strip()
    amount = clean_money(row[cols["last_gift_amount"]]) if cols["last_gift_amount"] else ""
    date = clean_date(row[cols["last_gift_date"]]) if cols["last_gift_date"] else ""
    return ", ".join(p for p in (amount, date) if p)


def convert(input_path, output_path):
    df = pd.read_csv(input_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if df.empty:
        print("Input CSV has no rows.")
        return

    cols = resolve_columns(df.columns)

    if not cols["name"] and not (cols["first_name"] or cols["last_name"]):
        print("ERROR: couldn't find a Name column (or First/Last Name columns) "
              "in the source CSV. Call Time requires a name for every contact.")
        sys.exit(1)

    print("Detected column mapping:")
    for field in ("name", "first_name", "last_name", "phone", "email",
                   "address", "street", "city", "state", "zip",
                   "organization", "occupation", "ask",
                   "last_gift_combined", "last_gift_amount", "last_gift_date",
                   "notes", "category"):
        if cols[field]:
            print(f"  {field:20s} <- '{cols[field]}'")

    out_rows = []
    missing_name = 0
    no_contact_info = 0
    unrecognized_categories = set()
    phone_warnings = 0

    for _, row in df.iterrows():
        name = build_name(row, cols)
        review_notes = []

        if not name:
            missing_name += 1
            review_notes.append("Missing name — Call Time will silently skip this row")

        phone_raw = str(row[cols["phone"]]).strip() if cols["phone"] else ""
        email = str(row[cols["email"]]).strip() if cols["email"] else ""
        phone, phone_warning = clean_phone(phone_raw)
        if phone_warning:
            phone_warnings += 1
            review_notes.append(phone_warning)

        if not phone and not email:
            no_contact_info += 1
            review_notes.append("No phone or email on file")

        category_raw = str(row[cols["category"]]).strip() if cols["category"] else ""
        category = normalize_category(category_raw)
        if category is None:
            if category_raw:
                unrecognized_categories.add(category_raw)
                review_notes.append(f"Unrecognized status '{category_raw}' — left blank")
            category = ""

        out_rows.append({
            "Name": name,
            "Phone": phone,
            "Email": email,
            "Address": build_address(row, cols),
            "City": build_city(row, cols),
            "Organization": str(row[cols["organization"]]).strip() if cols["organization"] else "",
            "Occupation": str(row[cols["occupation"]]).strip() if cols["occupation"] else "",
            "Ask": clean_money(row[cols["ask"]]) if cols["ask"] else "",
            "Last Gift": build_last_gift(row, cols),
            "Notes": str(row[cols["notes"]]).strip() if cols["notes"] else "",
            "Category": category,
            "Review Notes": "; ".join(review_notes),
        })

    out_df = pd.DataFrame(out_rows, columns=OUTPUT_COLUMNS)
    out_df.to_excel(output_path, index=False, engine="openpyxl")

    print(f"\nWrote {len(out_df)} rows to {output_path}")
    if missing_name:
        print(f"  WARNING: {missing_name} row(s) missing a name — Call Time will silently drop these on import.")
    if no_contact_info:
        print(f"  NOTE: {no_contact_info} row(s) have neither phone nor email.")
    if phone_warnings:
        print(f"  NOTE: {phone_warnings} phone number(s) didn't look like standard 10-digit numbers — left as-is.")
    if unrecognized_categories:
        print(f"  NOTE: unrecognized status/category values (left blank): {', '.join(sorted(unrecognized_categories))}")
    print("  See the 'Review Notes' column in the output file for row-by-row flags "
          "(that column is ignored by Call Time's import — just for your review).")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input_csv", help="Path to the source donor-data CSV")
    parser.add_argument("-o", "--output", help="Output .xlsx path (default: <input>_calltime.xlsx)")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    if not input_path.exists():
        print(f"ERROR: {input_path} not found")
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.with_name(input_path.stem + "_calltime.xlsx")
    convert(input_path, output_path)


if __name__ == "__main__":
    main()
