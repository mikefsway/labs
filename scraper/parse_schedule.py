"""
Step 3: Parse a UKAS schedule PDF into structured capability records.

Each PDF has:
- Page 1: Header with lab name, accreditation number, address, contact, website
- Pages 2+: Two tables per page:
    - Table 0: Repeating header banner (skip)
    - Table 1: Three-column capability table:
        - Materials/Products tested
        - Type of test / Properties measured / Range of measurement
        - Standard specifications / Equipment / Techniques used
"""

import json
import re
import sys
from pathlib import Path

import pdfplumber


def parse_header(page) -> dict:
    """Extract header information from the first page of a schedule PDF."""
    text = page.extract_text() or ""
    lines = text.split("\n")

    header = {
        "lab_name": "",
        "accreditation_number": "",
        "issue_number": "",
        "issue_date": "",
        "address_lines": [],
        "contact": "",
        "phone": "",
        "email": "",
        "website": "",
        "standard": "",
        "site_info": "",
    }

    # Also try to extract from the first table (header banner)
    tables = page.extract_tables()
    if tables:
        for table in tables:
            for row in table:
                for cell in row:
                    if not cell:
                        continue
                    if "Issue No:" in cell:
                        m = re.search(r"Issue No:\s*(\d+)", cell)
                        if m:
                            header["issue_number"] = m.group(1)
                        m = re.search(r"Issue date:\s*(.+?)$", cell, re.MULTILINE)
                        if m:
                            header["issue_date"] = m.group(1).strip()
                    if "Contact:" in cell:
                        m = re.search(r"Contact:\s*(.+?)$", cell, re.MULTILINE)
                        if m:
                            header["contact"] = m.group(1).strip()
                    if "Tel:" in cell:
                        m = re.search(r"Tel:\s*(.+?)$", cell, re.MULTILINE)
                        if m:
                            header["phone"] = m.group(1).strip()
                    if "E-Mail:" in cell or "E-mail:" in cell:
                        m = re.search(r"E-[Mm]ail:\s*(\S+)", cell)
                        if m:
                            header["email"] = m.group(1).strip()
                    if "Website:" in cell:
                        m = re.search(r"Website:\s*(\S+)", cell)
                        if m:
                            header["website"] = m.group(1).strip()
                    if "Testing performed" in cell or "Calibration performed" in cell:
                        header["site_info"] = cell.strip()

    # Extract accreditation number from text or table cells
    for line in lines:
        line = line.strip()
        if re.match(r"^\d{4,5}$", line):
            header["accreditation_number"] = line
    # Also check table cells for accreditation number (e.g. "22061\nAccredited to...")
    if not header["accreditation_number"] and tables:
        for table in tables:
            for row in table:
                for cell in row:
                    if cell and "Accredited to" in cell:
                        m = re.match(r"(\d{4,5})\s*\n", cell)
                        if m:
                            header["accreditation_number"] = m.group(1)

    # Lab name: look in the header table for the cell with the company name
    if tables:
        for table in tables:
            for row in table:
                for cell in row:
                    if not cell:
                        continue
                    cell_lines = cell.strip().split("\n")
                    first_line = cell_lines[0].strip()
                    # The lab name cell starts with the company name,
                    # then has Issue No on the next line
                    if "Issue No:" in cell and first_line and "Issue No" not in first_line:
                        header["lab_name"] = first_line
                    # Or it might be a standalone cell with just the name
                    elif (
                        len(cell_lines) <= 2
                        and first_line
                        and "Schedule" not in first_line
                        and "United Kingdom" not in first_line
                        and "UKAS" not in first_line
                        and "Accredited" not in first_line
                        and "performed" not in first_line
                        and "Pine Trees" not in first_line
                        and not re.match(r"^\d{4,5}$", first_line)
                        and "Contact:" not in first_line
                    ):
                        # Could be the lab name
                        pass

    # Standard: extract from text or table cells
    for line in lines:
        line = line.strip()
        if "Accredited to" in line:
            m = re.search(r"(ISO/IEC\s*\d+:\d+)", text)
            if m:
                header["standard"] = m.group(1)
    if not header["standard"] and tables:
        for table in tables:
            for row in table:
                for cell in row:
                    if cell and "ISO/IEC" in cell:
                        m = re.search(r"(ISO/IEC\s*\d+:\d+)", cell)
                        if m:
                            header["standard"] = m.group(1)

    # Get address from the cell block between lab name and contact
    if tables:
        for table in tables:
            for row in table:
                for cell in row:
                    if not cell:
                        continue
                    # The address cell contains multiple lines with street, city, postcode
                    cell_lines = [l.strip() for l in cell.strip().split("\n")]
                    # Check if this looks like an address block
                    has_postcode = any(re.search(r"[A-Z]{1,2}\d{1,2}\s*\d[A-Z]{2}", l) for l in cell_lines)
                    if has_postcode and len(cell_lines) >= 2:
                        # Filter out contact info lines that got merged with address
                        addr_lines = []
                        for l in cell_lines:
                            if any(marker in l for marker in [
                                "Contact:", "Tel:", "Fax:", "E-Mail:", "E-mail:",
                                "Website:", "Address",
                            ]):
                                continue
                            addr_lines.append(l)
                        if addr_lines and not header["address_lines"]:
                            header["address_lines"] = addr_lines

    header["address"] = ", ".join(header["address_lines"]) if header["address_lines"] else ""
    del header["address_lines"]

    return header


def is_header_banner_table(table) -> bool:
    """Check if a table is the repeating page header banner (not capability data)."""
    if not table or len(table) < 1:
        return False
    # Header banners contain these markers in any cell
    banner_markers = [
        "Schedule of Accreditation",
        "United Kingdom Accredita",
        "Pine Trees",
        "Accredited to",
        "Issue No:",
    ]
    for row in table[:3]:
        for cell in row:
            if cell and any(m in cell for m in banner_markers):
                return True
    return False


def is_column_header_row(row) -> bool:
    """Check if a row is a column header (not data)."""
    combined = " ".join((c or "") for c in row)
    header_markers = [
        "Materials/Products",
        "Type of test",
        "Measured Quantity",
        "Instrument or Gauge",
        "Expanded\nMeasurement",
        "Expanded Measurement",
        "Expa nded",  # OCR artifact variant
        "Location details",
        "Location\ncode",
    ]
    return any(m in combined for m in header_markers)


def parse_capability_tables(pdf) -> list[dict]:
    """Extract capability rows from the capability tables across all pages."""
    capabilities = []

    for page_num, page in enumerate(pdf.pages):
        tables = page.extract_tables()

        for table in tables:
            if not table:
                continue

            # Skip entire header banner tables
            if is_header_banner_table(table):
                continue

            for row in table:
                if not row or len(row) < 3:
                    continue

                # Skip column header rows
                if is_column_header_row(row):
                    continue

                col0 = (row[0] or "").strip()
                col1 = (row[1] or "").strip()
                col2 = (row[2] or "").strip()

                # Some calibration tables have an extra empty column after col0
                # (6 cols where col1 is empty and real data is in cols 2-5)
                if len(row) >= 5 and not col1 and col0:
                    # Check if col2 looks like range data or col3 has uncertainty
                    col3 = (row[3] or "").strip()
                    if col2 or col3:
                        col1 = col2
                        col2 = col3

                # Skip metadata rows
                skip_markers = [
                    "Accredited to",
                    "ISO/IEC 17025",
                    "Testing performed",
                    "Calibration performed",
                    "Issue No:",
                ]
                combined = col0 + col1 + col2
                if any(m in combined for m in skip_markers):
                    continue

                # Skip location detail rows (multi-site PDFs)
                # These contain "Address" + contact info or "Local contact"
                if "Local contact" in combined:
                    continue
                if col0.startswith("Address") or col0.startswith("At customer"):
                    continue
                # Skip rows about customer premises or site suitability
                if "customer" in combined.lower() or "Client Premises" in combined:
                    continue
                if "All sites suitable" in combined or "All locations suitable" in combined:
                    continue
                # Skip rows that are just contact info
                if col1.startswith("Local Contact:") or col1.startswith("Local contact:"):
                    continue

                # Skip empty rows
                if not col0 and not col1 and not col2:
                    continue

                # Skip rows that are just location codes (short, no real data)
                all_short = all(len(c) <= 5 for c in [col0, col1, col2] if c)
                if all_short and not any(c for c in [col0, col1, col2] if len(c) > 3):
                    continue

                # Skip section-header-only rows (e.g. "RANGE IN MILLIMETRES...")
                # These span the full width and have no data in other cols
                if col0 and not col1 and not col2:
                    # Check if it's a section header (ALL CAPS, no actual test data)
                    if col0.isupper() and len(col0) > 20:
                        continue

                # Clean up "As listed on Page X"
                if col0.startswith("As listed on"):
                    col0 = ""

                capabilities.append({
                    "materials_products": col0,
                    "test_type": col1,
                    "standards": col2,
                    "page": page_num + 1,
                })

    return capabilities


def extract_test_section_id(test_type: str) -> str | None:
    """Extract the most specific test section number from a test_type string.

    E.g. "1 EMC TESTING\n1.1 MILITARY...\n1.1.1 Conducted Emissions" -> "1.1.1"
    """
    # Find all section numbers, take the most specific (deepest) one
    matches = re.findall(r'(\d+(?:\.\d+)+)\s+[A-Z]', test_type)
    if matches:
        return max(matches, key=lambda m: m.count('.'))
    # Single top-level number
    m = re.match(r'^(\d+)\s+[A-Z]', test_type)
    if m:
        return m.group(1)
    return None


def is_continuation_of_previous(cap: dict, prev: dict | None) -> bool:
    """Determine if a capability row is a continuation of the previous entry
    (i.e. more standards for the same test), rather than a new test type."""
    if not prev:
        return False

    test_text = cap["test_type"]

    # If it explicitly says "(cont'd)" and has the same section number, it's a continuation
    if "(cont'd)" in test_text or "(cont" in test_text[:30]:
        # Extract the actual test section from this row
        new_id = extract_test_section_id(test_text)
        prev_id = extract_test_section_id(prev["test_type"])
        if new_id and prev_id and new_id == prev_id:
            return True
        # Different section number means new capability
        if new_id and prev_id and new_id != prev_id:
            return False
        # If we can't determine, treat as continuation
        return True

    # Empty test type with just standards = continuation
    if not test_text and cap["standards"]:
        return True

    return False


def merge_continuation_rows(capabilities: list[dict]) -> list[dict]:
    """Merge rows that continue the previous entry (more standards for same test).

    A new test section (different section number) creates a new capability,
    even if materials_products is empty.
    """
    merged = []

    for cap in capabilities:
        if is_continuation_of_previous(cap, merged[-1] if merged else None):
            prev = merged[-1]
            if cap["standards"]:
                prev["standards"] += "\n" + cap["standards"]
            # Carry forward materials if previous was empty
            if cap["materials_products"] and not prev["materials_products"]:
                prev["materials_products"] = cap["materials_products"]
        else:
            entry = cap.copy()
            # Clean up "(cont'd)" noise from test_type
            test = entry["test_type"]
            # Remove parent section cont'd lines, keep the actual test line
            lines = test.split("\n")
            cleaned = [l for l in lines if "(cont'd)" not in l and "(cont" not in l[:15]]
            if cleaned:
                entry["test_type"] = "\n".join(cleaned)
            merged.append(entry)

    return merged


def split_by_test_section(capabilities: list[dict]) -> list[dict]:
    """Split capabilities that contain multiple numbered test sections.

    Within a single merged capability, the test_type field may contain
    multiple sections like "1.1.1 Conducted Emissions\n...\n1.1.2 Radiated Emissions\n..."
    Split these into separate capability records.
    """
    result = []

    for cap in capabilities:
        test_text = cap["test_type"]
        standards_text = cap["standards"]

        # Find section numbers like "1.1.1", "1.1.2", "2.1", etc.
        # This is a simple split that works for most cases
        sections = re.split(r'\n(?=\d+\.\d+(?:\.\d+)?\s+[A-Z])', test_text)
        std_sections = re.split(r'\n(?=[A-Z]{2,})', standards_text)

        if len(sections) <= 1:
            result.append(cap)
        else:
            # For now, keep as single record but note there are subsections
            # More sophisticated splitting would need to align standards
            result.append(cap)

    return result


def parse_schedule(pdf_path: str) -> dict:
    """Parse a complete schedule PDF into structured data."""
    with pdfplumber.open(pdf_path) as pdf:
        header = parse_header(pdf.pages[0])
        raw_capabilities = parse_capability_tables(pdf)
        capabilities = merge_continuation_rows(raw_capabilities)

    # Reject non-schedule documents (no accreditation number = guidance doc, not a lab)
    if not header["accreditation_number"]:
        return {
            "header": header,
            "capabilities": [],
            "total_pages": len(pdfplumber.open(pdf_path).pages),
            "source_pdf": str(pdf_path),
        }

    # Clean up header standard field (remove embedded newlines)
    header["standard"] = header["standard"].replace("\n", " ").strip()

    # Filter out noise: empty capabilities, "END" markers, section-only headers
    cleaned = []
    for cap in capabilities:
        # Skip "END" marker
        if cap["materials_products"].strip() == "END":
            continue
        # Skip entries with no standards (these are section headers, not capabilities)
        if not cap["standards"].strip():
            continue
        cleaned.append(cap)

    return {
        "header": header,
        "capabilities": cleaned,
        "total_pages": len(pdfplumber.open(pdf_path).pages),
        "source_pdf": str(pdf_path),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_schedule.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    result = parse_schedule(pdf_path)

    print(f"Lab: {result['header']['lab_name']}")
    print(f"Accreditation #: {result['header']['accreditation_number']}")
    print(f"Address: {result['header']['address']}")
    print(f"Contact: {result['header']['contact']}")
    print(f"Phone: {result['header']['phone']}")
    print(f"Email: {result['header']['email']}")
    print(f"Website: {result['header']['website']}")
    print(f"Standard: {result['header']['standard']}")
    print(f"Pages: {result['total_pages']}")
    print(f"Capabilities found: {len(result['capabilities'])}")
    print()

    for i, cap in enumerate(result["capabilities"]):
        mat = cap["materials_products"][:80] if cap["materials_products"] else "(cont'd)"
        test = cap["test_type"].split("\n")[0][:80]
        stds = cap["standards"].split("\n")[0][:80]
        print(f"  [{i+1}] Materials: {mat}")
        print(f"      Test: {test}")
        print(f"      Standards: {stds}")
        num_standards = len([l for l in cap["standards"].split("\n") if l.strip()])
        print(f"      ({num_standards} standard references)")
        print()

    # Save full output
    out_path = Path(pdf_path).with_suffix(".json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Full output saved to {out_path}")


if __name__ == "__main__":
    main()
