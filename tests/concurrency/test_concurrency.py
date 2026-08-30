import concurrent.futures
from fastapi.testclient import TestClient
from issue_hub.main import app
from issue_hub.config import settings

client = TestClient(app)
headers = {"Authorization": f"Bearer {settings.api_token}"}

def create_single_issue():
    """Worker task to send a single issue create request."""
    # We use a unique title to prevent any duplicate content checks
    payload = {
        "severity": "LOW",
        "description": "Concurrency test payload.",
        "project": "tessallite",
        "repository": "tessallite-workspace"
    }
    response = client.post("/api/v1/issues", json=payload, headers=headers)
    return response.status_code, response.json()

def test_concurrency_zero_collision_allocation():
    """Launch 100 parallel create requests to verify zero-collision sequence allocation (Section 34.1)."""
    num_requests = 100
    
    # Run the parallel creations using a ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(create_single_issue) for _ in range(num_requests)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
    # Analyze results
    success_count = 0
    allocated_ids = set()
    allocated_seqs = set()
    
    for status_code, data in results:
        assert status_code == 200
        assert data["ok"] is True
        
        issue = data["issue"]
        issue_id = issue["issue_id"]
        seq_num = issue["sequence_number"]
        
        success_count += 1
        allocated_ids.add(issue_id)
        allocated_seqs.add(seq_num)
        
    # Verify that we succeeded 100 times and have exactly 100 unique non-colliding IDs and sequence numbers
    assert success_count == num_requests
    assert len(allocated_ids) == num_requests
    assert len(allocated_seqs) == num_requests
    print(f"Concurrency check passed! Allocated {num_requests} issues with 0 collisions.")
