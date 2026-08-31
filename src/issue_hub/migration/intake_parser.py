import re
from typing import Dict, Any, Optional

def parse_intake_file(content: str, filename_id: str) -> Optional[Dict[str, Any]]:
    """Parse a single legacy markdown intake file (Gate 4 / Section 5)."""
    lines = content.splitlines()
    if not lines:
        return None
        
    metadata = {}
    description_lines = []
    
    # Check if the file uses frontmatter --- delimiters
    if lines[0].strip() == "---":
        frontmatter_lines = []
        in_frontmatter = True
        for line in lines[1:]:
            if in_frontmatter:
                if line.strip() == "---":
                    in_frontmatter = False
                else:
                    frontmatter_lines.append(line)
            else:
                description_lines.append(line)
        for fl in frontmatter_lines:
            if ":" in fl:
                k, v = fl.split(":", 1)
                metadata[k.strip().lower()] = v.strip()
    else:
        # Direct metadata lines (no --- delimiter - Gate 4 / Section 5)
        # Included real workspace keys like 'temp_id', 'note', and 'resolution'
        VALID_KEYS = {
            "status", "severity", "area", "title", "refs", "project", "repository", 
            "branch", "worktree", "task", "priority", "expected_effort", "domain", 
            "category", "classification", "owner", "aka", "duplicate_of", "related_to", 
            "resolution", "source", "tags", "created_at", "updated_at", "reopen_count",
            "calculated_effort", "recommended_next_step", "temp_id", "note", "aka_alias", "promoted_bug"
        }
        in_metadata = True
        for line in lines:
            if in_metadata:
                if ":" in line:
                    parts = line.split(":", 1)
                    k = parts[0].strip().lower()
                    if k in VALID_KEYS:
                        metadata[k] = parts[1].strip()
                        continue
                # Blank lines are skipped or switch metadata parsing
                if not line.strip():
                    continue
                # If a line does not match a valid metadata key, we switch to description parsing
                in_metadata = False
                description_lines.append(line)
            else:
                description_lines.append(line)
            
    # Description parsing
    desc_content = "\n".join(description_lines).strip()
    
    # Strip leading markdown headings from description if they exactly mirror the title
    title_val = metadata.get("title", "")
    if title_val:
        escaped_title = re.escape(title_val)
        desc_clean = re.sub(rf"^#+\s+{escaped_title}\s*\n*", "", desc_content, flags=re.IGNORECASE).strip()
    else:
        desc_clean = desc_content
        
    # Resolve canonical issue_id and temp_id (Gate 4 / Section 5)
    # Check if a valid Bug-N or TMP-N is in the filename_id
    bug_match = re.search(r"\b(Bug-\d+)\b", filename_id, re.IGNORECASE)
    tmp_match = re.search(r"\b(TMP-\d+)\b", filename_id, re.IGNORECASE)
    
    canonical_id = None
    temp_id = metadata.get("temp_id") or metadata.get("aka") or metadata.get("note")
    
    if bug_match:
        canonical_id = bug_match.group(1)
    elif tmp_match:
        temp_id = tmp_match.group(1)
        
    if not canonical_id:
        # It's a pending intake! We keep the full filename_id as the primary identity
        issue_id = filename_id
        is_pending = True
    else:
        # It's a promoted intake! It maps to an existing canonical ID
        issue_id = canonical_id
        is_pending = False
    
    # Extract sequence number from ID if possible
    seq_match = re.search(r"(\d+)$", issue_id)
    seq_num = int(seq_match.group(1)) if seq_match else 0
    
    # Resolve project code
    project = metadata.get("project")
    if not project:
        id_parts = filename_id.split("-")
        if len(id_parts) > 2:
            project = id_parts[0]
            
    return {
        "issue_id": issue_id,
        "is_pending": is_pending,
        "temp_id": temp_id,
        "sequence_number": seq_num,
        "project": project,
        "repository": metadata.get("repository"),
        "branch": metadata.get("branch", "main"),
        "worktree": metadata.get("worktree"),
        "task": metadata.get("task"),
        "status": metadata.get("status", "OPEN").upper(),
        "severity": metadata.get("severity", "HIGH").upper(),
        "priority": metadata.get("priority"),
        "expected_effort": metadata.get("expected_effort", "UNKNOWN").upper(),
        "title": title_val or filename_id,
        "description": desc_clean or desc_content,
        "area": metadata.get("area"),
        "classification": metadata.get("classification"),
        "domain": metadata.get("domain"),
        "category": metadata.get("category"),
        "refs": metadata.get("refs"),
        "source": metadata.get("source"),
        "aka": metadata.get("aka"),
        "owner": metadata.get("owner"),
        "recommended_next_step": metadata.get("recommended_next_step"),
        "tags": [t.strip() for t in metadata.get("tags", "").split(",") if t.strip()] if metadata.get("tags") else [],
        "is_retired": False,
        "legacy_raw": content.strip()
    }
