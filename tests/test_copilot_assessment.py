"""Tests for assess_copilot_repos.py new checks (Copilot files)."""
import json
from unittest.mock import patch
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import assess_copilot_repos as acr


class TestCheckCopilotFiles:
    """Tests for additional Copilot file detection."""
    
    @patch('assess_copilot_repos.run_gh_command')
    def test_all_files_present(self, mock_cmd):
        mock_cmd.side_effect = [
            {"name": "copilot-instructions.md"},  # .github/copilot-instructions.md
            {"name": "AGENTS.md"},  # AGENTS.md
            {"name": ".copilotignore"},  # .copilotignore
            {"name": "mcp.json"},  # .github/copilot/mcp.json
        ]
        result = acr.check_copilot_files({"nameWithOwner": "org/repo"})
        assert result['has_copilot_instructions'] is True
        assert result['has_agents_md'] is True
        assert result['has_copilotignore'] is True
        assert result['has_mcp_config'] is True
    
    @patch('assess_copilot_repos.run_gh_command')
    def test_no_files_present(self, mock_cmd):
        mock_cmd.return_value = None
        result = acr.check_copilot_files({"nameWithOwner": "org/repo"})
        assert result['has_copilot_instructions'] is False
        assert result['has_agents_md'] is False
        assert result['has_copilotignore'] is False
        assert result['has_mcp_config'] is False
    
    @patch('assess_copilot_repos.run_gh_command')
    def test_partial_files(self, mock_cmd):
        mock_cmd.side_effect = [
            {"name": "copilot-instructions.md"},  # present
            None,  # AGENTS.md absent
            None,  # .copilotignore absent
            {"name": "mcp.json"},  # present
        ]
        result = acr.check_copilot_files({"nameWithOwner": "org/repo"})
        assert result['has_copilot_instructions'] is True
        assert result['has_agents_md'] is False
        assert result['has_copilotignore'] is False
        assert result['has_mcp_config'] is True
