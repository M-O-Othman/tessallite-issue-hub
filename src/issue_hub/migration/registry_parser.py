import re
from typing import Dict, Any, List, Optional

# Regex to parse legacy markdown line (Section 23.5)
# Example: - **Bug-9627** — `[OPEN]` — AKA XMLA-9627 — `[HIGH -- XMLA title]` Description. Area: ...
LINE_REGEX = re.compile(
    r"^\s*-\s+\*\*(?P<id>[^*]+)\*\*\s+—\s+`\[(?P<status>[^\]]+)\]`"
    r"(\s+—\s+AKA\s+(?P<aka>[^—]+))?"
    r"\s+—\s+`\[(?P<severity>[^-]+)\s+--\s+(?P<title>[^\]]+)\]`"
    r"\s*(?P<rest>.*)$"
)

def parse_registry_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single line of a legacy markdown registry list."""
    match = LINE_REGEX.match(line)
    if not match:
        return None
        
    group = match.groupdict()
    issue_id = group["id"].strip()
    status = group["status"].strip()
    aka = group["aka"].strip() if group["aka"] else None
    severity = group["severity"].strip()
    title = group["title"].strip()
    rest = group["rest"].strip()
    
    # Extract project from ID, e.g., TESS-Bug-9627 -> TESS, or default to None
    project = None
    id_parts = issue_id.split("-")
    if len(id_parts) > 2:
        project = id_parts[0]
    
    # Parse inline metadata from description text
    # e.g., "Description text. Area: Gateway. Refs: src/xmla.py:45. Domain: gateway. Category: product."
    # We use a positive lookahead to lazily extract fields stopping before the next capitalised keyword
    def extract_field(field_name: str, text: str) -> Optional[str]:
        pattern = rf"\b{field_name}:\s*(.*?)(?=\b(?:Area|Refs|Domain|Category|Owner|Source):|$)"
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            return val.rstrip(".").strip() # strip trailing periods
        return None

    area = extract_field("Area", rest)
    refs = extract_field("Refs", rest)
    domain = extract_field("Domain", rest)
    category = extract_field("Category", rest)
    owner = extract_field("Owner", rest)
    source = extract_field("Source", rest)
    
    # Keep the full rich description text from rest so no information is lost (Section 23)
    desc_clean = rest.strip()
    if desc_clean.endswith("."):
        desc_clean = desc_clean[:-1].strip()

    # Extract sequence number from ID
    seq_match = re.search(r"-(\d+)$", issue_id)
    seq_num = int(seq_match.group(1)) if seq_match else 0
    
    return {
        "issue_id": issue_id,
        "sequence_number": seq_num,
        "project": project,
        "status": status,
        "aka": aka,
        "severity": severity,
        "title": title,
        "description": desc_clean or title,
        "area": area,
        "refs": refs,
        "domain": domain,
        "category": category,
        "owner": owner,
        "source": source,
        "tags": [],
        "is_retired": False,
        "legacy_raw": line.strip()
    }

def parse_registry_file(content: str) -> List[Dict[str, Any]]:
    """Parse all lines of a legacy registry markdown document."""
    records = []
    for line in content.splitlines():
        if line.strip().startswith("- **"):
            record = parse_registry_line(line)
            if record:
                records.append(record)
    return records
