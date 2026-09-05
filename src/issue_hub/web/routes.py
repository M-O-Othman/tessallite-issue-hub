from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text, func
from sqlalchemy.orm import Session
import bcrypt
import json
import markdown
import logging
import html
import secrets
from html.parser import HTMLParser
from typing import Optional
from pathlib import Path
from datetime import datetime

from issue_hub.database import get_db
from issue_hub.config import settings
from issue_hub.models import Issue, IssueHistory, LookupValue, HubSetting
from issue_hub.issue_service import create_issue, update_issue, get_project_key_template
from issue_hub.schemas import CreateIssueRequest, UpdateIssueRequest, UpdateIssueRequestSet, RetireRequest
from issue_hub.search import build_issue_query, apply_sort, resolve_limit, parse_sort
from issue_hub.filters import IssueFilterParams, issue_filters
from issue_hub.pagination import build_page, clamp_offset
from issue_hub import ui_config

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


def load_lookups(db: Session) -> dict:
    """Load every active lookup list used by the filter UI.

    Shared by the issue list and the analytics dashboard so both offer the same
    filter vocabulary.
    """
    lookups = {}
    for name, lookup_type in ui_config.LOOKUP_LISTS.items():
        columns = [LookupValue.value, LookupValue.label]
        if lookup_type == "STATUS":
            columns.append(LookupValue.is_terminal)
        lookups[name] = db.query(*columns).filter(
            LookupValue.lookup_type == lookup_type,
            LookupValue.is_active.is_(True),
        ).order_by(LookupValue.display_order, LookupValue.value).all()
    return lookups


def apply_global_project(request: Request, filters: IssueFilterParams) -> IssueFilterParams:
    """Apply the site-wide project selector when no explicit project is chosen."""
    global_project = request.cookies.get("global_project")
    if not filters.values.get("project") and global_project and global_project.strip() and global_project != "ALL":
        filters.values["project"] = [global_project.strip()]
    return filters


@router.get("/", response_class=HTMLResponse)
def get_issues_list(
    request: Request,
    filters: IssueFilterParams = Depends(issue_filters),
    db: Session = Depends(get_db),
):
    """Render the issue list.

    Binds to the same filter dependency as the REST API and the analytics
    dashboard, so an identical query string returns an identical result set.
    """
    if not is_authenticated(request):
        return redirect_to_login()

    filters = apply_global_project(request, filters)
    lookups = load_lookups(db)

    kwargs = filters.to_query_kwargs()
    base = build_issue_query(db, **kwargs)
    total = base.count()

    # Resolve the page size once; every rendered number derives from this value
    # rather than from what the client asked for.
    effective_limit = resolve_limit(db, filters.limit)
    offset = clamp_offset(filters.offset, total, effective_limit)

    items = (
        apply_sort(base, filters.sort, kwargs.get("q"))
        .limit(effective_limit)
        .offset(offset)
        .all()
    )
    page = build_page(total=total, limit=effective_limit, offset=offset, count=len(items))

    parsed_sort = parse_sort(filters.sort)

    # Header summary counts, scoped by the active project context.
    statuses = lookups["statuses"]
    open_statuses = [row[0] for row in statuses if not row[2]]
    closed_statuses = [row[0] for row in statuses if row[2]]

    def scoped(query):
        project = filters.values.get("project")
        return query.filter(Issue.project.in_(project)) if project else query

    counts = {
        "all": scoped(db.query(Issue)).count(),
        "open": scoped(db.query(Issue).filter(Issue.status.in_(open_statuses), Issue.is_retired.is_(False))).count(),
        "closed": scoped(db.query(Issue).filter(Issue.status.in_(closed_statuses), Issue.is_retired.is_(False))).count(),
        "reserved": scoped(db.query(Issue).filter(Issue.status == "RESERVED", Issue.is_retired.is_(False))).count(),
        "retired": scoped(db.query(Issue).filter(Issue.is_retired.is_(True))).count(),
    }

    return templates.TemplateResponse(
        request,
        "list.html",
        {
            "items": [i.to_dict() for i in items],
            "filters": filters,
            "page": page,
            "sort_columns": ui_config.LIST_SORT_COLUMNS,
            "sort_field": parsed_sort[0] if parsed_sort else None,
            "sort_direction": parsed_sort[1] if parsed_sort else None,
            "counts": counts,
            **lookups,
        },
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
def get_visualization(
    request: Request,
    filters: IssueFilterParams = Depends(issue_filters),
    db: Session = Depends(get_db),
):
    """Render the analytics dashboard.

    Filtering happens in SQL through the same query builder the issue list uses,
    so every chart and KPI on the page reflects exactly the filters in the URL
    and the two surfaces cannot disagree.
    """
    if not is_authenticated(request):
        return redirect_to_login()

    filters = apply_global_project(request, filters)
    lookups = load_lookups(db)

    # Project only the columns the charts read. Serialising every field would
    # inline megabytes of description and legacy text into the page.
    fields = ui_config.ANALYTICS_PROJECTION_FIELDS
    rows = build_issue_query(db, **filters.to_query_kwargs()).with_entities(
        *[getattr(Issue, name) for name in fields]
    ).all()

    def serialise(row) -> dict:
        record = {}
        for name, value in zip(fields, row):
            record[name] = value.isoformat() if isinstance(value, datetime) else value
        return record

    # Escape literal '</script>' so issue content cannot close the script tag early.
    issues_json = json.dumps([serialise(r) for r in rows], default=str) \
        .replace("</script>", "<\\/script>").replace("</Script>", "<\\/Script>")

    terminal_statuses = [
        value for value, in db.query(LookupValue.value).filter(
            LookupValue.lookup_type == "STATUS",
            LookupValue.is_terminal.is_(True),
        ).all()
    ]

    return templates.TemplateResponse(
        request,
        "visualization.html",
        {
            "issues_json": issues_json,
            "terminal_statuses_json": json.dumps(terminal_statuses),
            "result_count": len(rows),
            "filters": filters,
            "dimensions": ui_config.ANALYTICS_DIMENSIONS,
            "severity_colors_json": json.dumps(ui_config.SEVERITY_COLORS),
            "treemap_palette_json": json.dumps(ui_config.TREEMAP_PALETTE),
            **lookups,
        },
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
