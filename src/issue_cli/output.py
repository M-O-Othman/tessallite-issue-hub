import json
import sys
from typing import Dict, Any

def print_success(data: Dict[str, Any]) -> None:
    """Print successful response as JSON and exit with 0."""
    print(json.dumps(data, indent=2))
    sys.exit(0)

def print_error(exit_code: int, err_json: Dict[str, Any]) -> None:
    """Print failed response as JSON and exit with the specified exit code."""
    # Write to stdout as per Section 17.4 success/failure example
    print(json.dumps(err_json, indent=2))
    sys.exit(exit_code)
