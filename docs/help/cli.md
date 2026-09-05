# 2. Non-Interactive CLI (`issue`)

[Previous: REST APIs](apis.md) | [Home: Help Home](home.md) | [Next: Web UI Portal](frontend.md)

---

The `issue` command-line client is a zero-dependency Python utility designed for execution inside shell scripts and by autonomous AI agents.

### A. Configuration Precedence
The CLI evaluates parameters using a strict, predictable precedence chain:
1. **Command-Line Option Override** (e.g. `--url`, `--token`, `--project`, `--repository`, `--branch`)
2. **Environment Variables** (e.g. `ISSUE_HUB_URL`, `ISSUE_HUB_TOKEN`, `ISSUE_HUB_PROJECT`, `ISSUE_HUB_REPOSITORY`, `ISSUE_HUB_DEFAULT_BRANCH`)
3. **User Configuration File** loaded from OS-specific paths:
   - Linux/macOS: `~/.config/tessallite-issue-hub/config.json`
   - Windows: `%APPDATA%\Tessallite\IssueHub\config.json`

### B. Advisory Git Discovery
If options are absent, the CLI runs background, non-blocking subprocess commands to auto-discover parameters from the local repository context:
- **Worktree Path:** `git rev-parse --show-toplevel`
- **Current Branch:** `git rev-parse --abbrev-ref HEAD`
- **Repository Name:** Extracted from `git config --get remote.origin.url`

### C. Standard Command Examples

#### Create Complete Issue:
```bash
issue create --severity HIGH --priority P1 --expected-effort M --title "Dax timeout" --description "Timeout on multi-level filters." --domain gateway --category product
```

#### Reserve Number with Zero Details:
```bash
issue create --reserve
```

#### Search or Find:
```bash
issue find Bug-9627 --history
issue find "9627"
issue find "hierarchy owner mismatch" --domain scheduler --priority P1
```

#### Update Field or Append Description File:
```bash
issue update Bug-9627 --set status=MITIGATED --set expected_effort=S
issue update Bug-9627 --append-file closeout_details.md
```

#### Manage Tags:
```bash
issue update Bug-9627 --add-tag core --remove-tag temp
```

#### Retire Duplicate:
```bash
issue update Bug-9627 --retire DUPLICATE --duplicate-of Bug-9584 --retire-note "Identical path."
```

### D. Standard Exit Codes
- `0`: Success
- `2`: Invalid arguments or client command validation error
- `3`: Authentication failed
- `4`: Issue not found
- `5`: Service unavailable or network connection failed
- `6`: Server-side internal error


### Ordering and Paging `find`

`--sort` takes a column name and an optional direction, and also accepts `field:desc` or `-field`. Lookup-backed columns (status, severity, priority, expected effort) order by their configured rank rather than alphabetically. `--limit` and `--offset` page the results, and ordering is deterministic so paging never repeats or skips an issue.

```bash
issue find --sort "severity desc" --limit 20
issue find --sort "-updated_at" --limit 20 --offset 40
issue find --branch main --updated-after 01-09-2026
```

Context options supplied before the subcommand (`--project`, `--repository`, `--branch`, `--worktree`) apply to the search:

```bash
issue --project tessallite find --sort "severity desc"
```

---

[Previous: REST APIs](apis.md) | [Home: Help Home](home.md) | [Next: Web UI Portal](frontend.md)
