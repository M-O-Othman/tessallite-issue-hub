import subprocess
import json

def test_cli_help():
    """Verify that 'issue --help' returns successfully with standard usage information."""
    result = subprocess.run(["issue", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Tessallite Issue Hub" in result.stdout
    assert "create" in result.stdout
    assert "find" in result.stdout
    assert "update" in result.stdout

def test_cli_no_args():
    """Verify that calling 'issue' without a command returns an INVALID_REQUEST error."""
    result = subprocess.run(["issue"], capture_output=True, text=True)
    assert result.returncode == 2
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


def _parse(argv):
    """Parse CLI arguments in-process without invoking the network."""
    import sys
    from issue_cli.main import parse_args
    original = sys.argv
    try:
        sys.argv = ["issue"] + argv
        return parse_args()
    finally:
        sys.argv = original


def test_find_exposes_sort_limit_and_offset():
    """find offers the same ordering and paging controls as the API and web UI."""
    args = _parse(["find", "--sort", "severity desc", "--limit", "5", "--offset", "10"])
    assert args.sort == "severity desc"
    assert args.limit == 5
    assert args.offset == 10


def test_find_exposes_branch_and_updated_range_filters():
    """The API-only filters are reachable from the CLI too."""
    args = _parse([
        "find", "--branch", "main", "--worktree", "/w", "--task", "task-9",
        "--updated-after", "01-01-2026", "--updated-before", "31-12-2026",
    ])
    assert args.branch == "main"
    assert args.worktree == "/w"
    assert args.task == "task-9"
    assert args.updated_after == "01-01-2026"
    assert args.updated_before == "31-12-2026"


def test_global_context_options_survive_the_find_subcommand():
    """`issue --project X find` must keep X.

    The find subparser redeclares options that also exist globally. Without
    argparse.SUPPRESS its defaults overwrote the values supplied before the
    subcommand, silently dropping the caller's project, repository, branch and
    worktree.
    """
    args = _parse([
        "--project", "globalproj", "--repository", "globalrepo",
        "--branch", "globalbranch", "--worktree", "/global", "find",
    ])
    assert args.project == "globalproj"
    assert args.repository == "globalrepo"
    assert args.branch == "globalbranch"
    assert args.worktree == "/global"


def test_subcommand_options_still_override_global_ones():
    """A value given after the subcommand wins, as it always did."""
    args = _parse(["--project", "globalproj", "find", "--project", "subproj"])
    assert args.project == "subproj"
