from fastapi import APIRouter, Request, Depends, Form, HTTPException, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text, func
from sqlalchemy.orm import Session
import bcrypt
import markdown
import logging
import html
import secrets
from html.parser import HTMLParser
from typing import Optional, List
from pathlib import Path
from datetime import datetime

from issue_hub.database import get_db
from issue_hub.config import settings
from issue_hub.models import Issue, IssueHistory, LookupValue, HubSetting
from issue_hub.issue_service import create_issue, update_issue, get_project_key_template
from issue_hub.schemas import CreateIssueRequest, UpdateIssueRequest, UpdateIssueRequestSet, RetireRequest
from issue_hub.search import query_issues

logger = logging.getLogger("issue_hub.web")

router = APIRouter(tags=["Web UI"])

# Resolve template directory path. Check for Docker Workdir path first, fall back to relative path
templates_dir = Path("/app/src/issue_hub/web/templates")
if not templates_dir.is_dir():
    templates_dir = Path(__file__).parent / "templates"
    
templates = Jinja2Templates(directory=str(templates_dir))

def get_all_projects():
    from issue_hub.database import SessionLocal
    from issue_hub.models import LookupValue
    db = SessionLocal()
    try:
        return db.query(LookupValue.value, LookupValue.label).filter(
            LookupValue.lookup_type == "PROJECT",
            LookupValue.is_active.is_(True)
        ).all()
    except Exception:
        return []
    finally:
        db.close()

templates.env.globals["get_all_projects"] = get_all_projects

class SafeHTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self.safe_tags = {
            "p", "br", "strong", "em", "code", "pre", "ul", "ol", "li", 
            "a", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "blockquote"
        }

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.safe_tags:
            # Reconstruct allowed tag with sanitized attributes
            cleaned_attrs = []
            for attr, val in attrs:
                if tag.lower() == "a" and attr.lower() == "href":
                    val_lower = val.lower().strip()
                    # Block javascript:, data:, vbscript: protocols (stored XSS links - Gate 2 / Section 4)
                    if (val_lower.startswith("http://") or 
                        val_lower.startswith("https://") or 
                        val_lower.startswith("mailto:") or 
                        val_lower.startswith("/") or 
                        val_lower.startswith(".") or 
                        val_lower.startswith("#")):
                        cleaned_attrs.append((attr, val))
                elif attr.lower() == "title":
                    cleaned_attrs.append((attr, val))
            
            attr_str = "".join(f' {a}="{html.escape(v)}"' for a, v in cleaned_attrs)
            self.result.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag):
        if tag.lower() in self.safe_tags:
            self.result.append(f"</{tag}>")

    def handle_data(self, data):
        self.result.append(html.escape(data))

    def get_html(self):
        return "".join(self.result)

def sanitize_html(html_str: str) -> str:
    """Sanitize rendered HTML using a whitelist parser to prevent stored XSS (Gate 2 / Section 4)."""
    sanitizer = SafeHTMLSanitizer()
    sanitizer.feed(html_str)
    return sanitizer.get_html()

# Register Jinja2 filter for rendering Markdown
def filter_markdown(text: str) -> str:
    if not text:
        return ""
    # Render with standard markdown, converting newlines
    rendered = markdown.markdown(text, extensions=["nl2br"])
    # Sanitize HTML after rendering to prevent script injections and unsafe URLs (Gate 2 / Section 4)
    return sanitize_html(rendered)

templates.env.filters["markdown"] = filter_markdown

def get_csrf_token(request: Request) -> str:
    """Generate or retrieve a CSRF token for the current session (Gate 2)."""
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = secrets.token_hex(32)
    return request.session["csrf_token"]

def verify_csrf_token(request: Request, form_token: Optional[str]) -> bool:
    """Verify the submitted CSRF token matches the session token (Gate 2)."""
    if settings.env == "development":
        return True
    session_token = request.session.get("csrf_token")
    if not session_token or not form_token:
        return False
    return secrets.compare_digest(session_token, form_token)

templates.env.globals["get_csrf_token"] = get_csrf_token

def is_authenticated(request: Request) -> bool:
    return request.session.get("logged_in") is True

def login_required(request: Request):
    if not is_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

# Exception redirect handler
def redirect_to_login():
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", response_class=HTMLResponse)
def get_login(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "login.html", {"error": None})

@router.post("/login", response_class=HTMLResponse)
def post_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: Optional[str] = Form(None)
):
    # Verify CSRF Token (Gate 2)
    if settings.env != "development" and not verify_csrf_token(request, csrf_token):
        return templates.TemplateResponse(request, "login.html", {"error": "CSRF verification failed."})

    # Verify username
    if username != settings.web_username:
        return templates.TemplateResponse(request, "login.html", {"error": "Invalid username or password"})
        
    # Verify password against bcrypt hash
    try:
        passwd_bytes = password.encode("utf-8")
        hash_bytes = settings.web_password_hash.encode("utf-8")
        if bcrypt.checkpw(passwd_bytes, hash_bytes):
            request.session["logged_in"] = True
            request.session["username"] = username
            return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        
    return templates.TemplateResponse(request, "login.html", {"error": "Invalid username or password"})

@router.get("/logout")
def get_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/set-project")
def set_global_project(request: Request, project: Optional[str] = None):
    referer = request.headers.get("referer", "/")
    if "/login" in referer or "/logout" in referer:
        referer = "/"
    response = RedirectResponse(url=referer, status_code=status.HTTP_303_SEE_OTHER)
    if project:
        response.set_cookie("global_project", project, max_age=365 * 24 * 3600, path="/")
    else:
        response.delete_cookie("global_project", path="/")
    return response


@router.get("/", response_class=HTMLResponse)
def get_issues_list(
    request: Request,
    q: Optional[str] = None,
    project: Optional[List[str]] = Query(None),
    repository: Optional[List[str]] = Query(None),
    status: Optional[List[str]] = Query(None),
    severity: Optional[List[str]] = Query(None),
    priority: Optional[List[str]] = Query(None),
    domain: Optional[List[str]] = Query(None),
    category: Optional[List[str]] = Query(None),
    expected_effort: Optional[List[str]] = Query(None),
    area: Optional[str] = None,
    classification: Optional[str] = None,
    owner: Optional[str] = None,
    task: Optional[str] = None,
    worktree: Optional[str] = None,
    tag: Optional[str] = None,
    is_retired: Optional[str] = None,
    is_terminal: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    closed_after: Optional[str] = None,
    closed_before: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    if not is_authenticated(request):
        return redirect_to_login()
        
    def normalize_list(lst: Optional[List[str]]) -> Optional[List[str]]:
        if not lst:
            return None
        res = [item.strip() for item in lst if item and item.strip()]
        return res if res else None

    # Retrieve global project cookie context
    global_project = request.cookies.get("global_project")
    
    project_norm = normalize_list(project)
    # If no explicit project selected but site-wide project is active, filter by active global project
    if not project_norm and global_project and global_project.strip() and global_project != "ALL":
        project_norm = [global_project.strip()]
        
    repository_norm = normalize_list(repository)
    status_norm = normalize_list(status)
    severity_norm = normalize_list(severity)
    priority_norm = normalize_list(priority)
    domain_norm = normalize_list(domain)
    category_norm = normalize_list(category)
    expected_effort_norm = normalize_list(expected_effort)
    
    q_norm = q.strip() if q and q.strip() else None
    area_norm = area.strip() if area and area.strip() else None
    classification_norm = classification.strip() if classification and classification.strip() else None
    owner_norm = owner.strip() if owner and owner.strip() else None
    task_norm = task.strip() if task and task.strip() else None
    worktree_norm = worktree.strip() if worktree and worktree.strip() else None
    tag_norm = tag.strip() if tag and tag.strip() else None
    
    # Helper to parse dates in multiple formats, prioritizing DD-MM-YYYY (Gate 2)
    def parse_user_date(date_str: Optional[str], end_of_day: bool = False) -> Optional[datetime]:
        if not date_str or not date_str.strip():
            return None
        cleaned = date_str.strip()
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(cleaned, fmt)
                if end_of_day:
                    return dt.replace(hour=23, minute=59, second=59)
                return dt
            except ValueError:
                continue
        return None

    created_after_dt = parse_user_date(created_after, end_of_day=False)
    created_before_dt = parse_user_date(created_before, end_of_day=True)
    closed_after_dt = parse_user_date(closed_after, end_of_day=False)
    closed_before_dt = parse_user_date(closed_before, end_of_day=True)

    # Safe boolean parsing of parameters
    is_retired_bool: Optional[bool] = None
    if is_retired == "true":
        is_retired_bool = True
    elif is_retired == "false":
        is_retired_bool = False
        
    is_terminal_bool: Optional[bool] = None
    if is_terminal == "true":
        is_terminal_bool = True
    elif is_terminal == "false":
        is_terminal_bool = False
        
    # Query lookups for filtering lists
    projects = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "PROJECT", LookupValue.is_active.is_(True)).all()
    repositories = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "REPOSITORY", LookupValue.is_active.is_(True)).all()
    statuses = db.query(LookupValue.value, LookupValue.label, LookupValue.is_terminal).filter(LookupValue.lookup_type == "STATUS", LookupValue.is_active.is_(True)).all()
    severities = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "SEVERITY", LookupValue.is_active.is_(True)).all()
    priorities = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "PRIORITY", LookupValue.is_active.is_(True)).all()
    efforts = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "EFFORT", LookupValue.is_active.is_(True)).all()
    domains = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "DOMAIN", LookupValue.is_active.is_(True)).all()
    categories = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "CATEGORY", LookupValue.is_active.is_(True)).all()
    
    # Query issues using normalized parameters
    items, total = query_issues(
        db=db,
        q=q_norm,
        project=project_norm,
        repository=repository_norm,
        status=status_norm,
        severity=severity_norm,
        priority=priority_norm,
        expected_effort=expected_effort_norm,
        area=area_norm,
        domain=domain_norm,
        category=category_norm,
        classification=classification_norm,
        owner=owner_norm,
        task=task_norm,
        worktree=worktree_norm,
        tag=tag_norm,
        is_retired=is_retired_bool,
        is_terminal=is_terminal_bool,
        created_from=created_after_dt,
        created_to=created_before_dt,
        closed_from=closed_after_dt,
        closed_to=closed_before_dt,
        limit=limit,
        offset=offset,
    )
    
    # Header summary counts, dynamically affected by the active Project Selector context (Section 19.3)
    q_all = db.query(Issue)
    q_open = db.query(Issue).filter(Issue.status.in_([s[0] for s in statuses if not s[2]]), Issue.is_retired.is_(False))
    q_closed = db.query(Issue).filter(Issue.status.in_([s[0] for s in statuses if s[2]]), Issue.is_retired.is_(False))
    q_reserved = db.query(Issue).filter(Issue.status == "RESERVED", Issue.is_retired.is_(False))
    q_retired = db.query(Issue).filter(Issue.is_retired.is_(True))
    
    if project_norm:
        q_all = q_all.filter(Issue.project.in_(project_norm))
        q_open = q_open.filter(Issue.project.in_(project_norm))
        q_closed = q_closed.filter(Issue.project.in_(project_norm))
        q_reserved = q_reserved.filter(Issue.project.in_(project_norm))
        q_retired = q_retired.filter(Issue.project.in_(project_norm))
        
    count_all = q_all.count()
    count_open = q_open.count()
    count_closed = q_closed.count()
    count_reserved = q_reserved.count()
    count_retired = q_retired.count()
    
    return templates.TemplateResponse(
        request,
        "list.html",
        {
            "items": [i.to_dict() for i in items],
            "total": total,
            "limit": limit,
            "offset": offset,
            "q": q_norm or "",
            "project_filter": project_norm or [],
            "repository_filter": repository_norm or [],
            "status_filter": status_norm or [],
            "severity_filter": severity_norm or [],
            "priority_filter": priority_norm or [],
            "domain_filter": domain_norm or [],
            "category_filter": category_norm or [],
            "expected_effort_filter": expected_effort_norm or [],
            "area_filter": area_norm or "",
            "classification_filter": classification_norm or "",
            "owner_filter": owner_norm or "",
            "task_filter": task_norm or "",
            "worktree_filter": worktree_norm or "",
            "tag_filter": tag_norm or "",
            "is_retired_filter": is_retired_bool,
            "is_terminal_filter": is_terminal_bool,
            "created_after_filter": created_after_dt.strftime("%d-%m-%Y") if created_after_dt else "",
            "created_before_filter": created_before_dt.strftime("%d-%m-%Y") if created_before_dt else "",
            "closed_after_filter": closed_after_dt.strftime("%d-%m-%Y") if closed_after_dt else "",
            "closed_before_filter": closed_before_dt.strftime("%d-%m-%Y") if closed_before_dt else "",
            "projects": projects,
            "repositories": repositories,
            "statuses": statuses,
            "severities": severities,
            "priorities": priorities,
            "efforts": efforts,
            "domains": domains,
            "categories": categories,
            "counts": {
                "all": count_all,
                "open": count_open,
                "closed": count_closed,
                "reserved": count_reserved,
                "retired": count_retired,
            }
        }
    )


@router.get("/issues/create", response_class=HTMLResponse)
def get_create_issue(request: Request, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return redirect_to_login()
        
    projects = db.query(LookupValue).filter(LookupValue.lookup_type == "PROJECT", LookupValue.is_active.is_(True)).all()
    repositories = db.query(LookupValue).filter(LookupValue.lookup_type == "REPOSITORY", LookupValue.is_active.is_(True)).all()
    statuses = db.query(LookupValue).filter(LookupValue.lookup_type == "STATUS", LookupValue.is_active.is_(True)).all()
    severities = db.query(LookupValue).filter(LookupValue.lookup_type == "SEVERITY", LookupValue.is_active.is_(True)).all()
    priorities = db.query(LookupValue).filter(LookupValue.lookup_type == "PRIORITY", LookupValue.is_active.is_(True)).all()
    efforts = db.query(LookupValue).filter(LookupValue.lookup_type == "EFFORT", LookupValue.is_active.is_(True)).all()
    domains = db.query(LookupValue).filter(LookupValue.lookup_type == "DOMAIN", LookupValue.is_active.is_(True)).all()
    categories = db.query(LookupValue).filter(LookupValue.lookup_type == "CATEGORY", LookupValue.is_active.is_(True)).all()
    
    # Preview next allocated key
    # Fetch next val of sequence quietly without incrementing
    try:
        next_seq = db.execute(text("SELECT last_value + 1 FROM issue_number_seq")).scalar() or 1
    except Exception:
        next_seq = 1
        
    global_template = get_project_key_template(db, None)
    
    global_project = request.cookies.get("global_project")
    form_data = None
    if global_project and global_project != "ALL":
        form_data = {"project": global_project}
        
    return templates.TemplateResponse(
        request,
        "create.html",
        {
            "projects": projects,
            "repositories": repositories,
            "statuses": statuses,
            "severities": severities,
            "priorities": priorities,
            "efforts": efforts,
            "domains": domains,
            "categories": categories,
            "next_seq": next_seq,
            "global_template": global_template,
            "form_data": form_data,
            "error": None
        }
    )

@router.post("/issues/create", response_class=HTMLResponse)
def post_create_issue(
    request: Request,
    project: str = Form(...),
    repository: str = Form(...),
    branch: str = Form("main"),
    worktree: Optional[str] = Form(None),
    task: Optional[str] = Form(None),
    status_val: str = Form("OPEN"),
    severity: Optional[str] = Form(None),
    priority: Optional[str] = Form(None),
    expected_effort: str = Form("UNKNOWN"),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    area: Optional[str] = Form(None),
    classification: Optional[str] = Form(None),
    domain: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    refs: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    owner: Optional[str] = Form(None),
    aka: Optional[str] = Form(None),
    related_to: Optional[str] = Form(None),
    tags_raw: Optional[str] = Form(None),
    recommended_next_step: Optional[str] = Form(None),
    reserve: bool = Form(False),
    id: Optional[str] = Form(None),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if not is_authenticated(request):
        return redirect_to_login()
        
    # Verify CSRF Token (Gate 2)
    if settings.env != "development" and not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="CSRF verification failed.")

    tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
    
    try:
        # Construct the CreateIssueRequest schema and pass to issue_service
        req = CreateIssueRequest(
            project=project,
            repository=repository,
            branch=branch,
            worktree=worktree or None,
            task=task or None,
            status=status_val,
            severity=severity or None,
            priority=priority or None,
            expected_effort=expected_effort,
            title=title or None,
            description=description or None,
            area=area or None,
            classification=classification or None,
            domain=domain or None,
            category=category or None,
            refs=refs or None,
            source=source or None,
            owner=owner or None,
            aka=aka or None,
            related_to=related_to or None,
            recommended_next_step=recommended_next_step or None,
            tags=tags_list,
            reserve=reserve,
            id=id or None,
        )
        
        issue = create_issue(db, req)
        return RedirectResponse(url=f"/issues/{issue.issue_id}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Web issue creation failed: {e}")
        # Re-render form with error and preserve inputs (Gate 2 / Section 10)
        projects = db.query(LookupValue).filter(LookupValue.lookup_type == "PROJECT", LookupValue.is_active.is_(True)).all()
        repositories = db.query(LookupValue).filter(LookupValue.lookup_type == "REPOSITORY", LookupValue.is_active.is_(True)).all()
        statuses = db.query(LookupValue).filter(LookupValue.lookup_type == "STATUS", LookupValue.is_active.is_(True)).all()
        severities = db.query(LookupValue).filter(LookupValue.lookup_type == "SEVERITY", LookupValue.is_active.is_(True)).all()
        priorities = db.query(LookupValue).filter(LookupValue.lookup_type == "PRIORITY", LookupValue.is_active.is_(True)).all()
        efforts = db.query(LookupValue).filter(LookupValue.lookup_type == "EFFORT", LookupValue.is_active.is_(True)).all()
        domains = db.query(LookupValue).filter(LookupValue.lookup_type == "DOMAIN", LookupValue.is_active.is_(True)).all()
        categories = db.query(LookupValue).filter(LookupValue.lookup_type == "CATEGORY", LookupValue.is_active.is_(True)).all()
        return templates.TemplateResponse(
            request,
            "create.html",
            {
                "projects": projects,
                "repositories": repositories,
                "statuses": statuses,
                "severities": severities,
                "priorities": priorities,
                "efforts": efforts,
                "domains": domains,
                "categories": categories,
                "next_seq": 1,
                "global_template": "Bug-{number}",
                "error": str(e),
                "form_data": {
                    "project": project,
                    "repository": repository,
                    "branch": branch,
                    "worktree": worktree or "",
                    "task": task or "",
                    "status": status_val,
                    "severity": severity or "",
                    "priority": priority or "",
                    "expected_effort": expected_effort,
                    "title": title or "",
                    "description": description or "",
                    "area": area or "",
                    "classification": classification or "",
                    "domain": domain or "",
                    "category": category or "",
                    "refs": refs or "",
                    "source": source or "",
                    "owner": owner or "",
                    "aka": aka or "",
                    "related_to": related_to or "",
                    "tags_raw": tags_raw or "",
                    "recommended_next_step": recommended_next_step or "",
                    "reserve": reserve,
                    "id": id or ""
                }
            }
        )


@router.get("/issues/{issue_id}", response_class=HTMLResponse)
def get_issue_detail(request: Request, issue_id: str, error: Optional[str] = None, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return redirect_to_login()

    issue = db.query(Issue).filter(func.lower(Issue.issue_id) == func.lower(issue_id)).first()
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")

    # Fetch history timeline
    history_records = db.query(IssueHistory).filter(
        func.lower(IssueHistory.issue_id) == func.lower(issue_id)
    ).order_by(IssueHistory.history_id.desc()).all()

    # Load editable vocabularies
    projects = db.query(LookupValue).filter(LookupValue.lookup_type == "PROJECT", LookupValue.is_active.is_(True)).all()
    repositories = db.query(LookupValue).filter(LookupValue.lookup_type == "REPOSITORY", LookupValue.is_active.is_(True)).all()
    statuses = db.query(LookupValue).filter(LookupValue.lookup_type == "STATUS", LookupValue.is_active.is_(True)).all()
    severities = db.query(LookupValue).filter(LookupValue.lookup_type == "SEVERITY", LookupValue.is_active.is_(True)).all()
    priorities = db.query(LookupValue).filter(LookupValue.lookup_type == "PRIORITY", LookupValue.is_active.is_(True)).all()
    efforts = db.query(LookupValue).filter(LookupValue.lookup_type == "EFFORT", LookupValue.is_active.is_(True)).all()
    domains = db.query(LookupValue).filter(LookupValue.lookup_type == "DOMAIN", LookupValue.is_active.is_(True)).all()
    categories = db.query(LookupValue).filter(LookupValue.lookup_type == "CATEGORY", LookupValue.is_active.is_(True)).all()
    retire_reasons = db.query(LookupValue).filter(LookupValue.lookup_type == "RETIRE_REASON", LookupValue.is_active.is_(True)).all()

    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "issue": issue.to_dict(),
            "history": history_records,
            "projects": projects,
            "repositories": repositories,
            "statuses": statuses,
            "severities": severities,
            "priorities": priorities,
            "efforts": efforts,
            "domains": domains,
            "categories": categories,
            "retire_reasons": retire_reasons,
            "error": error
        }
    )

def render_detail_with_error(request: Request, issue_id: str, db: Session, error: str) -> HTMLResponse:
    """Helper to render issue detail page with error message (Gate 2 / Section 10)."""
    return get_issue_detail(request=request, issue_id=issue_id, error=error, db=db)

@router.post("/issues/{issue_id}/edit", response_class=HTMLResponse)
def post_edit_issue(
    request: Request,
    issue_id: str,
    project: str = Form(...),
    repository: str = Form(...),
    branch: str = Form("main"),
    worktree: Optional[str] = Form(None),
    task: Optional[str] = Form(None),
    status_val: str = Form("OPEN"),
    severity: Optional[str] = Form(None),
    priority: Optional[str] = Form(None),
    expected_effort: str = Form("UNKNOWN"),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    area: Optional[str] = Form(None),
    classification: Optional[str] = Form(None),
    domain: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    refs: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    owner: Optional[str] = Form(None),
    aka: Optional[str] = Form(None),
    related_to: Optional[str] = Form(None),
    tags_raw: Optional[str] = Form(None),
    recommended_next_step: Optional[str] = Form(None),
    created_at: Optional[str] = Form(None),
    updated_at: Optional[str] = Form(None),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    if not is_authenticated(request):
        return redirect_to_login()
        
    # Verify CSRF Token (Gate 2)
    if settings.env != "development" and not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="CSRF verification failed.")

    tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
    
    try:
        # Patch field updates
        patch = UpdateIssueRequest(
            set=UpdateIssueRequestSet(
                project=project,
                repository=repository,
                branch=branch,
                worktree=worktree or None,
                task=task or None,
                status=status_val,
                severity=severity or None,
                priority=priority or None,
                expected_effort=expected_effort,
                title=title,
                description=description or None,
                area=area or None,
                classification=classification or None,
                domain=domain or None,
                category=category or None,
                refs=refs or None,
                source=source or None,
                owner=owner or None,
                aka=aka or None,
                related_to=related_to or None,
                recommended_next_step=recommended_next_step or None,
                tags=tags_list,
            )
        )
        update_issue(db, issue_id, patch)

        # Update custom dates (created_at / updated_at) if provided (Gate 2)
        issue_model = db.query(Issue).filter(func.lower(Issue.issue_id) == func.lower(issue_id)).first()
        if issue_model:
            from datetime import datetime, timezone
            if created_at and created_at.strip():
                try:
                    dt = datetime.strptime(created_at.strip(), "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
                    issue_model.created_at = dt
                except ValueError:
                    pass
            if updated_at and updated_at.strip():
                try:
                    dt = datetime.strptime(updated_at.strip(), "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
                    issue_model.updated_at = dt
                except ValueError:
                    pass
            db.commit()
    except Exception as e:
        logger.error(f"Web edit failed: {e}")
        return render_detail_with_error(request, issue_id, db, str(e))
        
    return RedirectResponse(url=f"/issues/{issue_id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/issues/{issue_id}/append", response_class=HTMLResponse)
def post_append_description(
    request: Request,
    issue_id: str,
    append_text: str = Form(...),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    if not is_authenticated(request):
        return redirect_to_login()
        
    # Verify CSRF Token (Gate 2)
    if settings.env != "development" and not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="CSRF verification failed.")

    try:
        patch = UpdateIssueRequest(append_description=append_text)
        update_issue(db, issue_id, patch)
    except Exception as e:
        logger.error(f"Web append failed: {e}")
        return render_detail_with_error(request, issue_id, db, str(e))
        
    return RedirectResponse(url=f"/issues/{issue_id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/issues/{issue_id}/description", response_class=HTMLResponse)
def post_edit_description(
    request: Request,
    issue_id: str,
    description: str = Form(...),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    if not is_authenticated(request):
        return redirect_to_login()
        
    # Verify CSRF Token (Gate 2)
    if settings.env != "development" and not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="CSRF verification failed.")

    try:
        patch = UpdateIssueRequest(set=UpdateIssueRequestSet(description=description))
        update_issue(db, issue_id, patch)
    except Exception as e:
        logger.error(f"Web edit description failed: {e}")
        return render_detail_with_error(request, issue_id, db, str(e))
        
    return RedirectResponse(url=f"/issues/{issue_id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/issues/{issue_id}/retire", response_class=HTMLResponse)
def post_retire_issue(
    request: Request,
    issue_id: str,
    reason: str = Form(...),
    duplicate_of: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    if not is_authenticated(request):
        return redirect_to_login()
        
    # Verify CSRF Token (Gate 2)
    if settings.env != "development" and not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="CSRF verification failed.")

    try:
        patch = UpdateIssueRequest(
            retire=RetireRequest(
                reason=reason,
                duplicate_of=duplicate_of or None,
                note=note or None
            )
        )
        update_issue(db, issue_id, patch)
    except Exception as e:
        logger.error(f"Web retire failed: {e}")
        return render_detail_with_error(request, issue_id, db, str(e))
        
    return RedirectResponse(url=f"/issues/{issue_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/settings", response_class=HTMLResponse)
def get_settings_page(request: Request, error: Optional[str] = None, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return redirect_to_login()
        
    # Query lookups and settings for rendering
    lookups = db.query(LookupValue).order_by(LookupValue.lookup_type.asc(), LookupValue.display_order.asc()).all()
    settings_records = db.query(HubSetting).all()
    
    # Group lookups by type
    grouped_lookups = {}
    for lookup_val in lookups:
        grouped_lookups.setdefault(lookup_val.lookup_type, []).append(lookup_val)
        
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "lookups": grouped_lookups,
            "settings": {s.setting_key: s.setting_value for s in settings_records},
            "error": error
        }
    )

@router.post("/settings/template", response_class=HTMLResponse)
def post_update_template(
    request: Request,
    key_template: str = Form(...),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    from issue_hub.key_generation import validate_key_template
    if not is_authenticated(request):
        return redirect_to_login()
        
    # Verify CSRF Token (Gate 2)
    if settings.env != "development" and not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="CSRF verification failed.")
        
    try:
        # Validate template (Gate 3)
        validate_key_template(key_template)
        
        # Overwrite hub setting
        setting = db.query(HubSetting).filter(HubSetting.setting_key == "issue_key_template").first()
        if not setting:
            setting = HubSetting(setting_key="issue_key_template", setting_value={"template": key_template})
            db.add(setting)
        else:
            setting.setting_value = {"template": key_template}
        db.commit()
    except Exception as e:
        logger.error(f"Web update template failed: {e}")
        # Re-render with error message (Section 10)
        lookups = db.query(LookupValue).order_by(LookupValue.lookup_type.asc(), LookupValue.display_order.asc()).all()
        settings_records = db.query(HubSetting).all()
        grouped_lookups = {}
        for lookup_val in lookups:
            grouped_lookups.setdefault(lookup_val.lookup_type, []).append(lookup_val)
        return templates.TemplateResponse(
            request,
            "config.html",
            {
                "lookups": grouped_lookups,
                "settings": {s.setting_key: s.setting_value for s in settings_records},
                "error": str(e)
            }
        )
        
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/visualization", response_class=HTMLResponse)
def get_visualization(request: Request, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return redirect_to_login()
        
    import json
    # Retrieve global project cookie context
    global_project = request.cookies.get("global_project")
    query = db.query(Issue)
    if global_project and global_project != "ALL":
        query = query.filter(Issue.project == global_project)
    all_issues = query.all()
    # Escape literal '</script>' tags to prevent premature script tag closure in HTML templates (Gate 2)
    issues_json = json.dumps([i.to_dict() for i in all_issues], default=str).replace("</script>", "<\\/script>").replace("</Script>", "<\\/Script>")
    
    # Query terminal statuses for database-driven metrics calculations (Gate 3 / ANL-001)
    terminal_statuses = [
        val for val, in db.query(LookupValue.value).filter(
            LookupValue.lookup_type == "STATUS", 
            LookupValue.is_terminal.is_(True)
        ).all()
    ]
    terminal_statuses_json = json.dumps(terminal_statuses)
    
    # Query lookups for filtering lists
    projects = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "PROJECT", LookupValue.is_active.is_(True)).all()
    repositories = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "REPOSITORY", LookupValue.is_active.is_(True)).all()
    statuses = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "STATUS", LookupValue.is_active.is_(True)).all()
    severities = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "SEVERITY", LookupValue.is_active.is_(True)).all()
    domains = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "DOMAIN", LookupValue.is_active.is_(True)).all()
    categories = db.query(LookupValue.value, LookupValue.label).filter(LookupValue.lookup_type == "CATEGORY", LookupValue.is_active.is_(True)).all()
    
    return templates.TemplateResponse(
        request,
        "visualization.html",
        {
            "issues_json": issues_json,
            "terminal_statuses_json": terminal_statuses_json,
            "projects": projects,
            "repositories": repositories,
            "statuses": statuses,
            "severities": severities,
            "domains": domains,
            "categories": categories,
        }
    )

@router.get("/help", response_class=HTMLResponse)
def get_help_home(request: Request):
    if not is_authenticated(request):
        return redirect_to_login()
    return templates.TemplateResponse(request, "help/home.html", {})

@router.get("/help/apis", response_class=HTMLResponse)
def get_help_apis(request: Request):
    if not is_authenticated(request):
        return redirect_to_login()
    return templates.TemplateResponse(request, "help/apis.html", {})

@router.get("/help/cli", response_class=HTMLResponse)
def get_help_cli(request: Request):
    if not is_authenticated(request):
        return redirect_to_login()
    return templates.TemplateResponse(request, "help/cli.html", {})

@router.get("/help/frontend", response_class=HTMLResponse)
def get_help_frontend(request: Request):
    if not is_authenticated(request):
        return redirect_to_login()
    return templates.TemplateResponse(request, "help/frontend.html", {})

@router.get("/help/migration", response_class=HTMLResponse)
def get_help_migration(request: Request):
    if not is_authenticated(request):
        return redirect_to_login()
    return templates.TemplateResponse(request, "help/migration.html", {})

@router.get("/help/deployment", response_class=HTMLResponse)
def get_help_deployment(request: Request):
    if not is_authenticated(request):
        return redirect_to_login()
    return templates.TemplateResponse(request, "help/deployment.html", {})
