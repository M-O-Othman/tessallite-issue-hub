import re
from typing import Dict, Any, Optional

def parse_intake_file(content: str, filename_id: str) -> Optional[Dict[str, Any]]:
    """Parse a single legacy markdown intake file with YAML-like frontmatter (Section 23.6)."""
    lines = content.splitlines()
    if not lines:
        return None
        
    # Check for frontmatter start
    if lines[0].strip() != "---":
        return None
        
    frontmatter_lines = []
    description_lines = []
    in_frontmatter = True
    
    for line in lines[1:]:
        if in_frontmatter:
            if line.strip() == "---":
                in_frontmatter = False
            else:
                frontmatter_lines.append(line)
        else:
            description_lines.append(line)
            
    # Parse frontmatter keys
    metadata = {}
    for fl in frontmatter_lines:
        if ":" in fl:
            k, v = fl.split(":", 1)
            metadata[k.strip().lower()] = v.strip()
            
    # Description parsing
    desc_content = "\n".join(description_lines).strip()
    
    # Strip leading markdown headings from description if they exactly mirror the title
    title_val = metadata.get("title", "")
    if title_val:
        escaped_title = re.escape(title_val)
        desc_clean = re.sub(rf"^#+\s+{escaped_title}\s*\n*", "", desc_content, flags=re.IGNORECASE).strip()
    else:
        desc_clean = desc_content
    
    # Extract sequence number from ID if possible (e.g. TMP-1234 -> 1234)
    seq_match = re.search(r"(\d+)$", filename_id)
    seq_num = int(seq_match.group(1)) if seq_match else 0
    
    # Resolve project code
    # If not present in frontmatter, extract project part from ID prefix, e.g. TESS-TMP-1234 -> TESS
    project = metadata.get("project")
    if not project:
        id_parts = filename_id.split("-")
        if len(id_parts) > 2:
            project = id_parts[0]
            
    return {
        "issue_id": filename_id,
        "sequence_number": seq_num,
        "project": project,
        "status": metadata.get("status", "OPEN").upper(),
        "aka": metadata.get("aka"),
        "severity": metadata.get("severity", "UNSPECIFIED").upper(),
        "title": metadata.get("title", "Legacy Intake Issue"),
        "description": desc_clean or metadata.get("title", "Legacy Intake Issue"),
        "area": metadata.get("area"),
        "refs": metadata.get("refs"),
        "domain": metadata.get("domain"),
        "category": metadata.get("category"),
        "owner": metadata.get("owner"),
        "source": metadata.get("source") or "legacy-intake",
        "tags": [t.strip() for t in metadata.get("tags", "").split(",") if t.strip()] if "tags" in metadata else [],
        "is_retired": metadata.get("is_retired", "false").lower() in ("true", "1", "yes"),
        "legacy_raw": content.strip()
    }
