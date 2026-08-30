import urllib.request
import urllib.error
import urllib.parse
import json
from typing import Optional, Dict, Any

class CLIClientException(Exception):
    def __init__(self, exit_code: int, error_data: Dict[str, Any]):
        super().__init__(error_data.get("error", {}).get("message", "CLI Error"))
        self.exit_code = exit_code
        self.error_data = error_data

def send_request(
    base_url: str,
    method: str,
    path: str,
    token: str,
    payload: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute standard library HTTP request and return parsed JSON or raise CLIClientException."""
    url = base_url.rstrip("/") + path
    
    # Query parameters
    if params:
        # Filter out None values from params
        clean_params = {k: str(v) for k, v in params.items() if v is not None}
        if clean_params:
            url += "?" + urllib.parse.urlencode(clean_params)
            
    data_bytes = None
    headers = {
        "Accept": "application/json",
    }
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data_bytes = json.dumps(payload).encode("utf-8")
        
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = response.read().decode("utf-8")
            return json.loads(res_data)
    except urllib.error.HTTPError as e:
        # Read the error body
        try:
            err_body = e.read().decode("utf-8")
            err_json = json.loads(err_body)
        except Exception:
            err_json = {
                "ok": False,
                "error": {
                    "code": "SERVER_ERROR",
                    "message": f"HTTP Error {e.code}: {e.reason}",
                    "details": {}
                }
            }
            
        # Exit code mapping (Section 17.4)
        if e.code == 401:
            exit_code = 3
        elif e.code == 404:
            exit_code = 4
        elif e.code == 503:
            exit_code = 5
        elif e.code == 500:
            exit_code = 6
        else:
            exit_code = 2 # standard command/validation error
            
        raise CLIClientException(exit_code, err_json)
    except urllib.error.URLError as e:
        err_json = {
            "ok": False,
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": f"Service unavailable or network failure: {e.reason}",
                "details": {}
            }
        }
        raise CLIClientException(5, err_json)
    except Exception as e:
        err_json = {
            "ok": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": f"Client-side internal error: {str(e)}",
                "details": {}
            }
        }
        raise CLIClientException(6, err_json)
