import re
from typing import Dict, Any, List, Optional

# Regex to parse legacy markdown line (Section 23.5)
LINE_REGEX = re.compile(
    r"^\s*-\s+\*\*(?P<id>[^*]+)\*\*\s+—\s+`\[(?P<status>[^\]]+)\]`"
    r"(\s+—\s+AKA\s+(?P<aka>[^—]+))?"
    r"\s+—\s+`\[(?P<severity>[^-]+)\s+--\s+(?P<title>[^\]]+)\]`"
    r"\s*(?P<rest>.*)$"
)

def parse_registry_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single line of a legacy markdown registry list (High-Performance String Search)."""
    match = LINE_REGEX.match(line)
    if not match:
        return None
        
    group = match.groupdict()
    issue_id = group["id"].strip()
    raw_status = group["status"].strip()
    
    # Extract leading status word (Gate 4 / Section 5)
    status_parts = re.split(r"[\s—-]+", raw_status)
    status = status_parts[0].upper() if status_parts else "OPEN"
    
    aka = group["aka"].strip() if group["aka"] else None
    severity = group["severity"].strip()
    title = group["title"].strip()
    rest = group["rest"].strip()
    
    # Project extraction
    project = None
    id_parts = issue_id.split("-")
    if len(id_parts) > 2:
        project = id_parts[0]
        
    # High-performance, sub-microsecond inline metadata extraction using standard C-level string find()
    def extract_field(field_name: str, text: str) -> Optional[str]:
        marker = f"{field_name}: "
        idx = text.lower().find(marker.lower())
        if idx == -1:
            return None
            
        start = idx + len(marker)
        next_idx = len(text)
        # Find the earliest occurrence of any other metadata field starting after our marker
        for next_field in ["Area: ", "Refs: ", "Domain: ", "Category: ", "Owner: ", "Source: "]:
            f_idx = text.lower().find(next_field.lower(), start)
            if f_idx != -1 and f_idx < next_idx:
                next_idx = f_idx
                
        val = text[start:next_idx].strip()
        return val.rstrip(".").strip()

    area = extract_field("Area", rest)
    refs = extract_field("Refs", rest)
    domain = extract_field("Domain", rest)
    category = extract_field("Category", rest)
    owner = extract_field("Owner", rest)
    source = extract_field("Source", rest)
    
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
        "description": rest or title, # Keep full rest (preserves raw structure, extremely fast)
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
