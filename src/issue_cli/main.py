import argparse
import json
import subprocess
from typing import Dict, Any

from issue_cli.config import resolve_config
from issue_cli.client import send_request, CLIClientException
from issue_cli.output import print_success, print_error

def discover_git_context() -> Dict[str, str]:
    """Advisory auto-discovery of git repository, branch, and worktree (Section 17.5)."""
    context = {}
    try:
        # Run git commands and capture output quietly
        toplevel = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], 
            stderr=subprocess.DEVNULL, 
            text=True
        ).strip()
        context["worktree"] = toplevel
        
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
            stderr=subprocess.DEVNULL, 
            text=True
        ).strip()
        if branch and branch != "HEAD":
            context["branch"] = branch
            
        remote_url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"], 
            stderr=subprocess.DEVNULL, 
            text=True
        ).strip()
        if remote_url:
            # Extract repository name from url, e.g. git@github.com:owner/repo.git -> repo
            repo_part = remote_url.split("/")[-1]
            if repo_part.endswith(".git"):
                repo_part = repo_part[:-4]
            context["repository"] = repo_part
            
    except Exception:
        pass # Ignore failure silently
    return context

def parse_args():
    parser = argparse.ArgumentParser(
        description="Tessallite Issue Hub non-interactive CLI client",
        prog="issue"
    )
    # Global overrides
    parser.add_argument("--url", help="Override issue hub URL")
    parser.add_argument("--token", help="Override API bearer token")
    parser.add_argument("--project", help="Override project code")
    parser.add_argument("--repository", help="Override repository name")
    parser.add_argument("--branch", help="Override branch name")
    parser.add_argument("--worktree", help="Override worktree path")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # create command
    create_parser = subparsers.add_parser("create", help="Create a complete issue or reserve a number")
    create_parser.add_argument("--reserve", action="store_true", help="Reserve a sequence number without detail fields")
    create_parser.add_argument("--severity", help="Severity level (CRITICAL, HIGH, etc.)")
    create_parser.add_argument("--title", help="Short issue title")
    create_parser.add_argument("--description", help="Complete Markdown issue description")
    create_parser.add_argument("--description-file", help="File containing Markdown description")
    create_parser.add_argument("--area", help="Issue area")
    create_parser.add_argument("--domain", help="Issue domain")
    create_parser.add_argument("--category", help="Issue category")
    create_parser.add_argument("--json", help="Path to JSON file containing complete issue body")
    create_parser.add_argument("--id", help="Supply a pre-existing reserved ID to complete or update")

    # find command
    find_parser = subparsers.add_parser("find", help="Find an issue, search text, or list filtered issues")
    find_parser.add_argument("query", nargs="?", help="Specific issue ID (e.g. Bug-9627) or text search phrase")
    find_parser.add_argument("--status", help="Filter by status")
    find_parser.add_argument("--severity", help="Filter by severity")
    find_parser.add_argument("--repository", help="Filter by repository")
    find_parser.add_argument("--project", help="Filter by project")
    find_parser.add_argument("--is-retired", help="Filter by retired state (true/false)")
    find_parser.add_argument("--is-terminal", help="Filter by terminal state (true/false)")
    find_parser.add_argument("--history", action="store_true", help="Include modification history in the output")

    # update command
    update_parser = subparsers.add_parser("update", help="Update issue fields, append text, or retire the record")
    update_parser.add_argument("id", help="ID of the issue to update")
    update_parser.add_argument("--set", action="append", help="Set field values in format 'field=value'")
    update_parser.add_argument("--description", help="Update complete description text")
    update_parser.add_argument("--description-file", help="File containing updated description text")
    update_parser.add_argument("--append-file", help="File containing text to append to the description")
    update_parser.add_argument("--add-tag", action="append", help="Tag to add to the issue")
    update_parser.add_argument("--remove-tag", action="append", help="Tag to remove from the issue")
    update_parser.add_argument("--retire", choices=["DUPLICATE", "NOT_AN_ISSUE", "CREATED_IN_ERROR", "SUPERSEDED", "OTHER"], help="Retire reason")
    update_parser.add_argument("--duplicate-of", help="If retiring as DUPLICATE, specifies the target canonical issue ID")
    update_parser.add_argument("--retire-note", help="Optional explanation for retiring the issue")
    update_parser.add_argument("--json", help="Path to JSON patch document")

    return parser.parse_args()

def handle_create(args, config: Dict[str, Any]) -> Dict[str, Any]:
    # Determine the payload
    payload = {}
    
    if args.json:
        try:
            with open(args.json, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            print_error(2, {
                "ok": False,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": f"Failed to read/parse JSON file '{args.json}': {str(e)}",
                    "details": {}
                }
            })
    else:
        # Load description from file if specified
        desc = args.description
        if args.description_file:
            try:
                with open(args.description_file, "r", encoding="utf-8") as f:
                    desc = f.read()
            except Exception as e:
                print_error(2, {
                    "ok": False,
                    "error": {
                        "code": "INVALID_REQUEST",
                        "message": f"Failed to read description file '{args.description_file}': {str(e)}",
                        "details": {}
                    }
                })
                
        payload = {
            "reserve": args.reserve,
            "id": args.id,
            "severity": args.severity,
            "title": args.title,
            "description": desc,
            "area": args.area,
            "domain": args.domain,
            "category": args.category,
        }
        
    # Merge resolved config (project, repository, branch, worktree) - Gate 6 / Section 11
    # Precedence: explicit CLI -> env/user config -> Git discovery -> server default
    git_ctx = discover_git_context()
    
    payload["project"] = payload.get("project") or config["project"] or None
    payload["repository"] = payload.get("repository") or config["repository"] or git_ctx.get("repository") or None
    payload["branch"] = payload.get("branch") or config["branch"] or git_ctx.get("branch") or None
    payload["worktree"] = payload.get("worktree") or config["worktree"] or None # Do not auto-send worktree (Section 11)
    
    # Filter out None values
    payload = {k: v for k, v in payload.items() if v is not None}
    
    return send_request(config["url"], "POST", "/api/v1/issues", config["token"], payload=payload)

def handle_find(args, config: Dict[str, Any]) -> Dict[str, Any]:
    params = {
        "status": args.status,
        "severity": args.severity,
        "repository": args.repository or (config["repository"] if args.query is None else None),
        "project": args.project or (config["project"] if args.query is None else None),
        "is_retired": args.is_retired.lower() in ("true", "1", "yes") if args.is_retired else None,
        "is_terminal": args.is_terminal.lower() in ("true", "1", "yes") if args.is_terminal else None,
    }
    
    # Check query: exact ID vs text search
    is_exact_id = False
    if args.query:
        import re
        # Check if query matches exact ID style (ends with digits, or matches Bug-\d+)
        if re.match(r"^[A-Za-z0-9-]+-\d+$", args.query):
            params["id"] = args.query
            is_exact_id = True
        else:
            params["q"] = args.query
            
    # Send list request
    res = send_request(config["url"], "GET", "/api/v1/issues", config["token"], params=params)
    
    # Section 17.3 find Bug-9627 with --history returns issue AND history!
    if is_exact_id and args.history and res.get("items"):
        # Fetch history for the returned exact issue ID
        issue_id = res["items"][0]["issue_id"]
        hist_res = send_request(config["url"], "GET", f"/api/v1/issues/{issue_id}/history", config["token"])
        return {
            "ok": True,
            "issue": res["items"][0],
            "history": hist_res.get("items", [])
        }
        
    return res

def handle_update(args, config: Dict[str, Any]) -> Dict[str, Any]:
    payload = {}
    
    if args.json:
        try:
            with open(args.json, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            print_error(2, {
                "ok": False,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": f"Failed to read/parse JSON file '{args.json}': {str(e)}",
                    "details": {}
                }
            })
    else:
        set_fields = {}
        if args.set:
            for item in args.set:
                if "=" not in item:
                    print_error(2, {
                        "ok": False,
                        "error": {
                            "code": "INVALID_REQUEST",
                            "message": f"Invalid set format '{item}'. Must be field=value",
                            "details": {}
                        }
                    })
                k, v = item.split("=", 1)
                set_fields[k.strip()] = v.strip()
                
        if getattr(args, "description", None):
            set_fields["description"] = args.description
            
        if getattr(args, "description_file", None):
            try:
                with open(args.description_file, "r", encoding="utf-8") as f:
                    set_fields["description"] = f.read()
            except Exception as e:
                print_error(2, {
                    "ok": False,
                    "error": {
                        "code": "INVALID_REQUEST",
                        "message": f"Failed to read description file '{args.description_file}': {str(e)}",
                        "details": {}
                    }
                })

        append_desc = None
        if args.append_file:
            try:
                with open(args.append_file, "r", encoding="utf-8") as f:
                    append_desc = f.read()
            except Exception as e:
                print_error(2, {
                    "ok": False,
                    "error": {
                        "code": "INVALID_REQUEST",
                        "message": f"Failed to read append file '{args.append_file}': {str(e)}",
                        "details": {}
                    }
                })
                
        # Parse tags as atomic additions/removals (Gate 6 / Section 11)
        if getattr(args, "add_tag", None):
            set_fields["add_tags"] = list(args.add_tag)
        if getattr(args, "remove_tag", None):
            set_fields["remove_tags"] = list(args.remove_tag)

        payload = {
            "set": set_fields if set_fields else None,
            "append_description": append_desc,
        }
        
        if args.retire:
            payload["retire"] = {
                "reason": args.retire,
                "duplicate_of": args.duplicate_of,
                "note": args.retire_note
            }
            
        # Clean None keys
        payload = {k: v for k, v in payload.items() if v is not None}
        
    return send_request(config["url"], "PATCH", f"/api/v1/issues/{args.id}", config["token"], payload=payload)

def main():
    args = parse_args()
    if not args.command:
        print_error(2, {
            "ok": False,
            "error": {
                "code": "INVALID_REQUEST",
                "message": "No command specified. Use --help for usage details."
            }
        })

    # Resolve configuration based on precedence
    resolved_config = resolve_config(args)
    
    if not resolved_config["url"]:
        print_error(5, {
            "ok": False,
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "No Issue Hub URL configured. Set ISSUE_HUB_URL env variable or config.json.",
                "details": {}
            }
        })
        
    try:
        if args.command == "create":
            res = handle_create(args, resolved_config)
        elif args.command == "find":
            res = handle_find(args, resolved_config)
        elif args.command == "update":
            res = handle_update(args, resolved_config)
        else:
            print_error(2, {
                "ok": False,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": f"Unsupported command '{args.command}'",
                    "details": {}
                }
            })
            
        print_success(res)
    except CLIClientException as e:
        print_error(e.exit_code, e.error_data)
    except Exception as e:
        print_error(6, {
            "ok": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": f"Unexpected fatal error: {str(e)}",
                "details": {}
            }
        })

if __name__ == "__main__":
    main()
