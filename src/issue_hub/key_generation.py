import re
from typing import Optional

def normalize_segment(value: Optional[str]) -> str:
    """Normalize a template segment according to Section 34.3 rules:
    1. trim whitespace;
    2. convert path separators, spaces, and unsupported punctuation to `-`;
    3. collapse repeated `-` characters;
    4. preserve readable case;
    5. remove leading and trailing separators.
    """
    if not value:
        return ""
    
    # Trim whitespace
    val = value.strip()
    
    # Convert path separators, spaces, and unsupported punctuation (non-alphanumeric/non-dash) to '-'
    val = re.sub(r"[ /\\_@:,;?!.*()|\[\]{}]+", "-", val)
    
    # Collapse repeated '-' characters
    val = re.sub(r"-+", "-", val)
    
    # Remove leading and trailing '-'
    val = val.strip("-")
    
    return val

def render_issue_id(
    template: str,
    number: int,
    project: Optional[str] = None,
    repository: Optional[str] = None,
    branch: Optional[str] = None,
    task: Optional[str] = None,
    type_: Optional[str] = None,
) -> str:
    """Render and normalize an issue key according to template placeholders."""
    if "{number}" not in template:
        raise ValueError("Key template must contain '{number}' placeholder")
    
    # Normalize segment values
    norm_project = normalize_segment(project)
    norm_repo = normalize_segment(repository)
    norm_branch = normalize_segment(branch)
    norm_task = normalize_segment(task)
    norm_type = normalize_segment(type_)
    
    # Substitute placeholders (if optional placeholder is empty, it becomes "")
    rendered = template
    rendered = rendered.replace("{project}", norm_project)
    rendered = rendered.replace("{repository}", norm_repo)
    rendered = rendered.replace("{branch}", norm_branch)
    rendered = rendered.replace("{task}", norm_task)
    rendered = rendered.replace("{type}", norm_type)
    
    # Put number placeholder back if we want to clean separators before placing number,
    # or just substitute number directly. Let's substitute number directly.
    rendered = rendered.replace("{number}", str(number))
    
    # Clean up any formatting residue (multiple dashes, leading/trailing dashes)
    # This also naturally handles empty placeholders becoming consecutive dashes.
    rendered = re.sub(r"-+", "-", rendered)
    rendered = rendered.strip("-")
    
    # Validation rules
    if not rendered:
        raise ValueError("Rendered issue ID prefix cannot be empty")
        
    if len(rendered) > 200:
        raise ValueError(f"Rendered issue ID is too long ({len(rendered)} characters, max 200)")
        
    # Section 11.3: Number is the last rendered segment, ending with -<digits>
    suffix_pattern = rf"-{number}$"
    if not re.search(suffix_pattern, rendered):
        raise ValueError(f"Rendered issue ID must end with sequence number suffix '-{number}'")
        
    return rendered

def validate_key_template(template: str):
    """Validate issue key template format centrally (Gate 3 / Section 8)."""
    # 1. Must contain exactly one '{number}' placeholder
    if template.count("{number}") != 1:
        raise ValueError("Template must contain exactly one '{number}' placeholder.")
        
    # 2. Must end with '{number}'
    if not template.endswith("{number}"):
        raise ValueError("Template must end with the '{number}' placeholder.")
    
    # 3. Check for other placeholders to ensure only supported ones are used
    placeholders = re.findall(r"\{([^}]+)\}", template)
    supported = {"number", "project", "repository", "branch", "task", "type"}
    for p in placeholders:
        if p not in supported:
            raise ValueError(f"Unsupported placeholder '{{{p}}}'. Supported placeholders are: {{number}}, {{project}}, {{repository}}, {{branch}}, {{task}}, {{type}}.")
            
    # 4. Verify rendered template length is safe
    if len(template) > 100:
        raise ValueError("Template format is too long (maximum 100 characters).")
        
    # 5. Run a sample render to verify correctness (Gate 3 / Section 8)
    try:
        from issue_hub.key_generation import render_issue_id
        render_issue_id(
            template=template,
            number=9999,
            project="testproj",
            repository="testrepo",
            branch="testbranch",
            task="testtask",
            type_="testtype"
        )
    except Exception as e:
        raise ValueError(f"Invalid key template: sample render failed with error: {e}")
