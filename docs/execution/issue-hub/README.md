# Tessallite Issue Hub - Agent Guide

Tessallite Issue Hub is the sole authoritative system for issue registration, number allocation, and issue tracking. 

**Strict Mandates for All Agents:**
- **Do not** edit the old legacy active or closed markdown registries.
- **Do not** create local `issue-intake` files or generate temporary `TMP-*` identifiers.
- **Do not** invent or guess a canonical ID if the Hub service is unavailable.
- **Do use** the permanent `issue_id` (e.g., `Bug-9627`) in code comments, commit messages, plans, and documentation.
- **Do retire** duplicate or invalid issues; never delete them.

---

## 1. Installation & Setup

### Installation
The client is a zero-dependency CLI executable named `issue`, installable via `pipx` or standard pip:
```bash
pipx install tessallite-issue-hub-cli
```

### Configuration
The CLI resolves configuration by looking at:
1. Command-line flags (e.g., `--url`, `--token`)
2. Environment variables
3. Global user configuration file

**Recommended Environment Variables:**
Add these to your local configuration (do not commit tokens to Git):
```bash
export ISSUE_HUB_URL="https://your-hub-url.com"  # Or local http://localhost:8080
export ISSUE_HUB_TOKEN="your_secure_bearer_token"
export ISSUE_HUB_PROJECT="tessallite"
export ISSUE_HUB_REPOSITORY="tessallite-workspace"
```

**Global Configuration Files:**
Tokens may also be stored safely inside:
- **Linux/macOS:** `~/.config/tessallite-issue-hub/config.json`
- **Windows:** `%APPDATA%\Tessallite\IssueHub\config.json`

Example `config.json`:
```json
{
  "ISSUE_HUB_URL": "http://localhost:8080",
  "ISSUE_HUB_TOKEN": "your_secure_bearer_token",
  "ISSUE_HUB_PROJECT": "tessallite",
  "ISSUE_HUB_REPOSITORY": "tessallite-workspace"
}
```

---

## 2. Command Reference

### A. Create a Complete Issue
Use `issue create` to register a new issue with mandatory `severity` and `description` details:
```bash
issue create \
  --severity HIGH \
  --title "XMLA hierarchy owner mismatch" \
  --description "Excel cannot resolve the hierarchy owner and labels grouped attributes as (All)." \
  --area "Gateway / XMLA / Excel" \
  --domain gateway \
  --category product
```

You can also load a description from a local Markdown file:
```bash
issue create \
  --severity MEDIUM \
  --title "XMLA Excel Bug" \
  --description-file bug_details.md
```

### B. Reserve an ID Before Details are Ready
If you need an issue number immediately to place in code comments or plans before writing full details:
```bash
issue create --reserve
```
This creates a real issue row on the server with status `RESERVED` and a permanent ID. 
When ready to supply full details later, complete the reservation using its ID:
```bash
issue update Bug-9627 --set severity=HIGH --append-file details.md
```

### C. Find and Search Issues
The `find` command can be used for exact lookups, full-text searches, or filtering lists.

**Exact ID Lookup:**
```bash
issue find Bug-9627
```

**Include Modification History:**
```bash
issue find Bug-9627 --history
```

**Text Search (scored and ranked):**
```bash
issue find "hierarchy unique name"
```

**Filter List by Fields:**
```bash
issue find --status OPEN --severity HIGH --project tessallite
```

### D. Update Fields & Append Notes
Modify metadata fields on an existing issue:
```bash
issue update Bug-9627 --set status=FIXED-PENDING-VERIFICATION --set expected_effort=S
```

Append notes, implementation reviews, or closeout summaries directly to the description with an automatic timestamp:
```bash
issue update Bug-9627 --append-file closeout.md
```

### E. Retire Duplicates or Invalid Issues
Never delete an issue. If an issue is a duplicate or created in error, retire it with a reason:
```bash
issue update Bug-9627 \
  --retire DUPLICATE \
  --duplicate-of Bug-9584 \
  --retire-note "Identical root cause and code path"
```

Supported retirement reasons: `DUPLICATE`, `NOT_AN_ISSUE`, `CREATED_IN_ERROR`, `SUPERSEDED`, `OTHER`.

---

## 3. Recommended Description Skeleton

When creating issues, structure descriptions according to this standard structure:
```md
## Problem
[Clear, high-signal summary of the problem]

## Observed Behaviour
[What actually happens, log output, or error traces]

## Expected Behaviour
[What should happen instead]

## Evidence and Reproduction
[Paths to files, specific lines of code, or inputs to reproduce]
```

---

## 4. Exceptional Operational Behaviours

### Network Failures
If the central Hub service is unreachable, the CLI returns a service unavailable error. **Never** invent or fabricate a temporary ID. If offline, write your notes in an external unnumbered Markdown file and submit them to the Hub once the service is restored.

### Retry Behaviors
The Hub does not implement active transaction idempotency keys. If a network interruption occurs *after* a transaction successfully commits on the database but *before* you receive the response, retrying the create request will generate a second distinct issue. This is acceptable. Search can easily locate the duplicate, and you can retire it as `DUPLICATE` referencing the other issue ID.
