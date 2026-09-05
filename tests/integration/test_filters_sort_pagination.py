"""Sorting, pagination, filter parity, and API/web agreement.

Covers the defects fixed in the list/analytics/API remediation: missing sort,
stale offset on a new search, wrong pagination bounds, and divergence between
the REST API, the issue list, and the analytics dashboard.
"""
import json
import re

import pytest
from fastapi.testclient import TestClient

from issue_hub.config import settings
from issue_hub.main import app

client = TestClient(app, raise_server_exceptions=False)
headers = {"Authorization": f"Bearer {settings.api_token}"}

PROJECT = "sortfixture"
SEVERITY_CYCLE = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
STATUS_CYCLE = ["OPEN", "RESERVED", "DEFERRED"]
SEED_COUNT = 25


@pytest.fixture(autouse=True, scope="module")
def seeded_issues():
    """Insert a known, isolated fixture set and remove it afterwards."""
    from issue_hub.database import SessionLocal
    from issue_hub.models import Issue

    db = SessionLocal()
    try:
        db.query(Issue).filter(Issue.project == PROJECT).delete()
        db.commit()
        for n in range(SEED_COUNT):
            db.add(Issue(
                issue_id=f"Bug-9{n:04d}",
                sequence_number=90000 + n,
                project=PROJECT,
                repository=f"repo-{n % 3}",
                status=STATUS_CYCLE[n % len(STATUS_CYCLE)],
                severity=SEVERITY_CYCLE[n % len(SEVERITY_CYCLE)],
                priority=f"P{n % 3}",
                domain=f"domain-{n % 2}",
                category=f"category-{n % 2}",
                owner=f"owner-{n % 4}",
                title=f"Sort fixture issue {n:02d}",
                description="Fixture row for sorting and pagination tests.",
            ))
        db.commit()
        yield
    finally:
        db.query(Issue).filter(Issue.project == PROJECT).delete()
        db.commit()
        db.close()


def api_list(**params):
    params.setdefault("project", PROJECT)
    response = client.get("/api/v1/issues", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="module")
def web():
    """A logged-in web session."""
    session = TestClient(app)
    session.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    return session


def web_total(session, query: str) -> int:
    response = session.get(f"/{query}")
    assert response.status_code == 200, response.text
    return int(re.search(r"Issue Ledger \((\d+) results\)", response.text).group(1))


def analytics_rows(session, query: str) -> list:
    response = session.get(f"/visualization{query}")
    assert response.status_code == 200, response.text
    payload = re.search(r'id="issues-data">\s*(.*?)\s*</script>', response.text, re.S).group(1)
    return json.loads(payload)


# --- Sorting -----------------------------------------------------------------

@pytest.mark.parametrize("field", ["sequence_number", "title", "owner", "created_at", "updated_at"])
def test_sort_both_directions_orders_results(field):
    """Every advertised sort field orders ascending and descending."""
    ascending = [i[field] for i in api_list(sort=f"{field} asc", limit=SEED_COUNT)["items"]]
    descending = [i[field] for i in api_list(sort=f"{field} desc", limit=SEED_COUNT)["items"]]

    assert ascending == sorted(ascending)
    assert descending == sorted(descending, reverse=True)
    assert ascending == list(reversed(descending))


def test_sort_accepts_alternate_syntaxes():
    """'field desc', 'field:desc' and '-field' mean the same thing."""
    expected = [i["issue_id"] for i in api_list(sort="sequence_number desc", limit=SEED_COUNT)["items"]]
    for spelling in ("sequence_number:desc", "-sequence_number"):
        assert [i["issue_id"] for i in api_list(sort=spelling, limit=SEED_COUNT)["items"]] == expected


def test_unknown_and_non_column_sort_fields_are_rejected():
    """A bad sort field falls back to the default order instead of erroring."""
    default = [i["issue_id"] for i in api_list(limit=SEED_COUNT)["items"]]
    for bogus in ("bogus_field", "metadata", "query", "1; DROP TABLE issues"):
        assert [i["issue_id"] for i in api_list(sort=bogus, limit=SEED_COUNT)["items"]] == default


def test_lookup_backed_sort_uses_display_order_not_alphabetical():
    """Severity sorts CRITICAL, HIGH, MEDIUM, LOW - not alphabetically."""
    severities = [i["severity"] for i in api_list(sort="severity asc", limit=SEED_COUNT)["items"]]
    first_seen = list(dict.fromkeys(severities))
    assert first_seen == SEVERITY_CYCLE
    # Alphabetical ordering would place LOW before MEDIUM.
    assert first_seen != sorted(SEVERITY_CYCLE)

    # Status is lookup-ordered too: OPEN(0), RESERVED(8), DEFERRED(2) by display_order.
    statuses = [i["status"] for i in api_list(sort="status asc", limit=SEED_COUNT)["items"]]
    assert list(dict.fromkeys(statuses)) == ["OPEN", "DEFERRED", "RESERVED"]


# --- Pagination --------------------------------------------------------------

def test_paging_covers_every_row_exactly_once():
    """Stable ordering means no row is repeated or skipped across pages."""
    page_size = 7
    collected, offset = [], 0
    while True:
        payload = api_list(limit=page_size, offset=offset)
        if not payload["items"]:
            break
        collected.extend(i["issue_id"] for i in payload["items"])
        offset += page_size
        assert offset <= SEED_COUNT + page_size

    assert len(collected) == SEED_COUNT
    assert len(set(collected)) == SEED_COUNT


def test_paging_is_stable_under_a_tied_sort_key():
    """A sort key shared by many rows still yields a total order."""
    page_size = 5
    collected, offset = [], 0
    while offset < SEED_COUNT:
        payload = api_list(limit=page_size, offset=offset, sort="severity asc")
        collected.extend(i["issue_id"] for i in payload["items"])
        offset += page_size
    assert len(set(collected)) == SEED_COUNT


def test_total_is_independent_of_paging():
    """The reported total counts matches, not the rows on the page."""
    payload = api_list(limit=5, offset=0)
    assert payload["total"] == SEED_COUNT
    assert len(payload["items"]) == 5


def test_final_page_is_partial_and_bounded(web):
    """The last page reports the rows it actually holds."""
    payload = api_list(limit=10, offset=20)
    assert len(payload["items"]) == SEED_COUNT - 20

    response = web.get(f"/?project={PROJECT}&limit=10&offset=20")
    assert "Showing 21 to 25 of 25 issues" in response.text


def test_effective_limit_is_echoed_not_the_requested_one():
    """The API reports the limit it applied."""
    assert api_list(limit=5)["limit"] == 5
    # Above the ceiling the request is rejected rather than silently clamped.
    response = client.get("/api/v1/issues", params={"limit": 99999}, headers=headers)
    assert response.status_code == 422


def test_out_of_range_offset_falls_back_to_the_last_page(web):
    """Asking past the end shows the last real page, not an empty table."""
    response = web.get(f"/?project={PROJECT}&limit=10&offset=99999")
    assert response.status_code == 200
    assert "Showing 21 to 25 of 25 issues" in response.text


def test_list_page_does_not_persist_offset_into_the_filter_form(web):
    """A new search must start at page 1, so the form carries no offset."""
    response = web.get(f"/?project={PROJECT}&limit=5&offset=10")
    form = re.search(r'<form action="/" method="get" id="filter-form">(.*?)</form>', response.text, re.S).group(1)
    assert 'name="offset"' not in form


def test_pagination_links_preserve_active_filters(web):
    """Navigating pages keeps the filters the user chose."""
    response = web.get(f"/?project={PROJECT}&severity=HIGH&limit=2")
    assert f"project={PROJECT}" in response.text
    assert "severity=HIGH" in response.text


def test_sort_headers_are_rendered_and_drop_offset(web):
    """Column headers link to a re-sort that returns to page 1."""
    response = web.get(f"/?project={PROJECT}&limit=5&offset=10")
    assert "sort=sequence_number" in response.text
    assert "sort=severity" in response.text
    header_links = re.findall(r'href="/\?([^"]*sort=[^"]*)"', response.text)
    assert header_links
    assert all("offset=" not in link for link in header_links)


# --- Filter parity across surfaces -------------------------------------------

PARITY_QUERIES = [
    "",
    "&severity=HIGH",
    "&status=OPEN,RESERVED",
    "&priority=P1",
    "&domain=domain-0&category=category-1",
    "&owner=owner-2",
    "&q=fixture",
    "&is_retired=false",
    "&created_from=01-01-2000&created_to=31-12-2100",
]


@pytest.mark.parametrize("extra", PARITY_QUERIES)
def test_api_web_and_analytics_agree_on_the_same_filters(web, extra):
    """One query string must mean the same thing on all three surfaces."""
    query = f"?project={PROJECT}{extra}"
    api_total = api_list(**{"limit": SEED_COUNT})["total"] if not extra else None

    web_count = web_total(web, query)
    analytics_count = len(analytics_rows(web, query))
    api_count = client.get(f"/api/v1/issues{query}", headers=headers).json()["total"]

    assert web_count == analytics_count == api_count, (
        f"{query}: web={web_count} analytics={analytics_count} api={api_count}"
    )
    if api_total is not None:
        assert api_count == SEED_COUNT


def test_comma_separated_values_work_on_the_web_as_on_the_api(web):
    """The web accepts 'a,b' exactly as the API does."""
    repeated = web_total(web, f"?project={PROJECT}&status=OPEN&status=RESERVED")
    comma = web_total(web, f"?project={PROJECT}&status=OPEN,RESERVED")
    assert repeated == comma > 0


def test_legacy_date_parameter_aliases_still_work(web):
    """Existing bookmarks using created_after/created_before keep working."""
    canonical = web_total(web, f"?project={PROJECT}&created_from=01-01-2000&created_to=31-12-2100")
    legacy = web_total(web, f"?project={PROJECT}&created_after=01-01-2000&created_before=31-12-2100")
    assert canonical == legacy == SEED_COUNT


def test_web_exposes_the_api_only_filters(web):
    """id, branch and updated ranges are reachable from the web UI."""
    response = web.get("/")
    for name in ("id", "branch", "updated_from", "updated_to"):
        assert f'name="{name}"' in response.text

    assert web_total(web, "?id=Bug-90000") == 1


# --- Analytics ---------------------------------------------------------------

def test_analytics_ships_only_the_fields_the_charts_read(web):
    """Heavy text columns must not be inlined into the page."""
    rows = analytics_rows(web, f"?project={PROJECT}")
    assert rows
    for heavy in ("description", "legacy_raw", "aka", "refs", "recommended_next_step"):
        assert heavy not in rows[0]


def test_analytics_offers_two_independent_treemap_dimensions(web):
    """The treemap segments by two user-chosen dimensions, not one plus severity."""
    response = web.get("/visualization")
    assert 'id="treemap-dimension"' in response.text
    assert 'id="treemap-secondary"' in response.text
    assert "visibleMin" not in response.text


def test_analytics_exposes_the_full_list_filter_surface(web):
    """Analytics offers every filter the issue list does."""
    analytics = web.get("/visualization").text
    listing = web.get("/").text
    names = set(re.findall(r'name="([a-z_]+)"', listing)) - {"username", "password", "csrf_token"}
    missing = {n for n in names if f'name="{n}"' not in analytics}
    assert not missing, f"analytics is missing filters: {sorted(missing)}"
