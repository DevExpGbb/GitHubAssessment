"""Shared fixtures for GitHub Assessment tests."""
import json
import subprocess
import pytest


class MockCompletedProcess:
    """Mock subprocess.CompletedProcess for gh CLI calls."""
    
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def make_gh_mock(responses):
    """Create a mock for subprocess.run that returns predefined responses based on command content.
    
    Args:
        responses: dict mapping command substring patterns to (stdout_data, returncode) tuples.
                   If stdout_data is a dict/list, it will be JSON-serialized.
    """
    def mock_run(command, **kwargs):
        cmd_str = command if isinstance(command, str) else ' '.join(command)
        
        for pattern, (data, code) in responses.items():
            if pattern in cmd_str:
                if isinstance(data, (dict, list)):
                    stdout = json.dumps(data)
                elif data is None:
                    raise subprocess.CalledProcessError(code, cmd_str)
                else:
                    stdout = str(data)
                return MockCompletedProcess(stdout=stdout, returncode=code)
        
        # Default: command not found in patterns, raise error
        raise subprocess.CalledProcessError(1, cmd_str)
    
    return mock_run


@pytest.fixture
def mock_rate_limit():
    """Standard rate limit response."""
    return {
        "resources": {
            "core": {
                "remaining": 4999,
                "limit": 5000,
                "reset": 9999999999
            }
        }
    }
