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
