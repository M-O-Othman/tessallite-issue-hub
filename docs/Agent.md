# Tessallite Issue Hub - AI Agent Handbook

This document is the official operational guide for **AI Coding Agents** interacting with the Tessallite Issue Hub. 

---

## 1. Core Architectural Mandate

In highly autonomous environments, multiple AI coding agents run in **parallel** across overlapping codebase branches, isolated code trees, or distinct worktrees. 

To prevent **horizontal race conditions, Git merge collisions, and duplicate sequence allocations** that arise from manual file-based registries (e.g., editing a shared Markdown list on Git):
1. **The Issue Hub is the Single Source of Truth:** Every issue, bug registration, and sequence number allocation must be handled dynamically through the centralized Hub service.
2. **Never Generate Local Temp IDs:** Do not invent placeholder IDs (like `TMP-1234`) or modify historical lists inside the repository.
3. **Always Bind and Reference Canonical IDs:** Use the permanent `issue_id` returned by the Hub (e.g., `Bug-9627`) in your commit messages, pull requests, plan files, and source code comments.

---

## 2. Agent Workflow Protocol

When tasked with implementing a feature or fixing a bug, follow this exact workflow:

```
[Agent Started] ──> [Call CLI to Create/Reserve ID] ──> [Get Bug-N]
                             │
                             ▼
               [Place Bug-N in Code & Plans]
                             │
                             ▼
               [Implement & Verify Changes]
                             │
                             ▼
        [Call CLI to Update Status & Append Closeout]
```

### Step 1: Allocate a Canonical ID
Before modifying the codebase, register the task. 

- **If full details are ready:** Create a complete issue:
  ```bash
  issue create \
    --severity HIGH \
    --title "XMLA Dax timeout" \
    --description "Timeout on multi-level filters. See [User Guide](../../Docs/user-guide.md)." \
    --domain gateway \
    --category product
  ```
- **If details are still being researched:** Reserve an ID immediately to unblock plan drafting:
  ```bash
  issue create --reserve
  ```
  The Hub will return a permanent ID (e.g., `Bug-9644`) with status `RESERVED`.

### Step 2: Track, Search, and Verify Context
To search for overlapping work or verify if another agent is already resolving a similar issue, use the **Wide Search** capability:
```bash
# Performs a full database wide-search (OR matching) across every single column
issue find "XMLA Dax timeout"
```
You can query by status, severity, tags, authors, or even sequence numbers. If an exact ID match is located, read its details and historical logs before proceeding:
```bash
issue find Bug-9644 --history
```

### Step 3: Modify the Codebase
Integrate the canonical `Bug-N` ID inside:
- Code comments: `# Resolves Bug-9644`
- Unit/integration test descriptions.
- Action plans (e.g., `work/action-plan.md`).

### Step 4: Reassigning Temporary/Legacy IDs
If you encounter older temporary IDs (like `TMP-9999`) or need to update a reserved ID with a new canonical one across a massive codebase, use our cross-platform **ID Reassignment Script** located at `../scripts/reassign_issue.sh`:
```bash
# Usage: ./scripts/reassign_issue.sh <OLD_ID> <NEW_ID> <PATH>
./scripts/reassign_issue.sh Bug-9999 Bug-9644 src/
```
This script automatically performs a safe, case-insensitive, word-bounded replacement across all source and document files within the specified scope.

### Step 5: Complete and Closeout the Issue
Once your work is implemented and verified green, update the Hub:
- **Complete a Reservation:**
  ```bash
  issue update Bug-9644 --set status=OPEN --set severity=HIGH --append-file closeout_logs.md
  ```
- **Close or Terminate the Issue:**
  ```bash
  issue update Bug-9644 --set status=FIXED --append-file closeout_evidence.md
  ```
- **Retire as Duplicate (Never Delete):** If you discover that your task overlaps with another, do not delete it. Retire it cleanly:
  ```bash
  issue update Bug-9644 --retire DUPLICATE --duplicate-of Bug-9500 --retire-note "Identical root cause."
  ```

---

## 3. Related System Documentation
- For detailed command structures and environment overrides, read the [Agent Guide](../../docs/execution/issue-hub/README.md).
- For overall web dashboard capabilities and lookup seeds, read the [User Guide](../../Docs/user-guide.md).
