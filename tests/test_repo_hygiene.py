"""Tests for repo_hygiene_assessment.py new checks."""
import json
import subprocess
from unittest.mock import patch, MagicMock
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import repo_hygiene_assessment as rha


class TestCheckCodeowners:
    """Tests for CODEOWNERS detection."""
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_codeowners_in_root(self, mock_cmd):
        # Returns dict with 'name' → truthy → returns True on first call
        mock_cmd.return_value = {"name": "CODEOWNERS", "path": "CODEOWNERS"}
        result = rha.check_codeowners("org/repo")
        assert result is True
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_codeowners_in_github_dir(self, mock_cmd):
        mock_cmd.side_effect = [
            None,  # root not found
            {"name": "CODEOWNERS", "path": ".github/CODEOWNERS"},
        ]
        result = rha.check_codeowners("org/repo")
        assert result is True
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_no_codeowners(self, mock_cmd):
        mock_cmd.side_effect = [None, None]
        result = rha.check_codeowners("org/repo")
        assert result is False


class TestCheckLicense:
    """Tests for LICENSE detection."""
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_has_license_mit(self, mock_cmd):
        mock_cmd.return_value = {
            "license": {"key": "mit", "name": "MIT License", "spdx_id": "MIT"}
        }
        result = rha.check_license("org/repo")
        assert result['has_license'] is True
        assert result['spdx_id'] == "MIT"
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_no_license(self, mock_cmd):
        mock_cmd.return_value = None
        result = rha.check_license("org/repo")
        assert result['has_license'] is False


class TestCheckSecurityMd:
    """Tests for SECURITY.md detection."""
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_security_md_in_root(self, mock_cmd):
        mock_cmd.return_value = {"name": "SECURITY.md"}
        result = rha.check_security_md("org/repo")
        assert result is True
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_no_security_md(self, mock_cmd):
        mock_cmd.side_effect = [None, None]
        result = rha.check_security_md("org/repo")
        assert result is False


class TestCheckDependabotConfig:
    """Tests for dependabot.yml detection."""
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_has_dependabot_yml(self, mock_cmd):
        mock_cmd.return_value = {"name": "dependabot.yml"}
        result = rha.check_dependabot_config("org/repo")
        assert result is True
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_has_dependabot_yaml(self, mock_cmd):
        mock_cmd.side_effect = [None, {"name": "dependabot.yaml"}]
        result = rha.check_dependabot_config("org/repo")
        assert result is True
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_no_dependabot(self, mock_cmd):
        mock_cmd.side_effect = [None, None]
        result = rha.check_dependabot_config("org/repo")
        assert result is False


class TestCheckPrivateVulnReporting:
    """Tests for private vulnerability reporting."""
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_pvr_enabled(self, mock_cmd):
        mock_cmd.return_value = {"enabled": True}
        result = rha.check_private_vuln_reporting("org/repo")
        assert result is True
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_pvr_disabled(self, mock_cmd):
        mock_cmd.return_value = {"enabled": False}
        result = rha.check_private_vuln_reporting("org/repo")
        assert result is False
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_pvr_not_accessible(self, mock_cmd):
        mock_cmd.return_value = None
        result = rha.check_private_vuln_reporting("org/repo")
        assert result is False


class TestCheckStaleness:
    """Tests for stale repository detection."""
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_active_repo(self, mock_cmd):
        from datetime import datetime, timezone
        recent = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_cmd.return_value = {
            "pushed_at": recent,
            "archived": False,
            "size": 500
        }
        result = rha.check_staleness("org/repo")
        assert result['is_stale'] is False
        assert result['is_archived'] is False
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_stale_repo(self, mock_cmd):
        mock_cmd.return_value = {
            "pushed_at": "2020-01-01T00:00:00Z",
            "archived": False,
            "size": 500
        }
        result = rha.check_staleness("org/repo")
        assert result['is_stale'] is True
        assert result['is_archived'] is False
    
    @patch('repo_hygiene_assessment.run_gh_command')
    def test_archived_repo(self, mock_cmd):
        mock_cmd.return_value = {
            "pushed_at": "2020-01-01T00:00:00Z",
            "archived": True,
            "size": 500
        }
        result = rha.check_staleness("org/repo")
        assert result['is_archived'] is True
