"""Tests for security_assessment.py new checks (Actions, Deploy Keys, Webhooks)."""
import json
from unittest.mock import patch
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import security_assessment as sa


class TestCheckActionsSecurity:
    """Tests for GitHub Actions security configuration checks."""
    
    @patch('security_assessment.run_gh_command')
    def test_restrictive_actions_config(self, mock_cmd):
        mock_cmd.side_effect = [
            {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False},
            {"enabled": True, "allowed_actions": "selected"},
        ]
        result = sa.check_actions_security("org/repo")
        assert result['default_workflow_permissions'] == 'read'
        assert result['can_approve_prs'] is False
        assert result['allowed_actions'] == 'selected'
        assert result['is_restrictive'] is True
        assert result['error'] is None
    
    @patch('security_assessment.run_gh_command')
    def test_permissive_actions_config(self, mock_cmd):
        mock_cmd.side_effect = [
            {"default_workflow_permissions": "write", "can_approve_pull_request_reviews": True},
            {"enabled": True, "allowed_actions": "all"},
        ]
        result = sa.check_actions_security("org/repo")
        assert result['default_workflow_permissions'] == 'write'
        assert result['can_approve_prs'] is True
        assert result['allowed_actions'] == 'all'
        assert result['is_restrictive'] is False
    
    @patch('security_assessment.run_gh_command')
    def test_actions_not_accessible(self, mock_cmd):
        mock_cmd.side_effect = [None, None]
        result = sa.check_actions_security("org/repo")
        assert result['default_workflow_permissions'] == 'unknown'
        assert result['is_restrictive'] is False


class TestCheckDeployKeys:
    """Tests for deploy keys audit."""
    
    @patch('security_assessment.run_gh_command')
    def test_no_deploy_keys(self, mock_cmd):
        mock_cmd.return_value = []
        result = sa.check_deploy_keys("org/repo")
        assert result['total_keys'] == 0
        assert result['write_keys'] == 0
    
    @patch('security_assessment.run_gh_command')
    def test_read_only_keys(self, mock_cmd):
        mock_cmd.return_value = [
            {"id": 1, "title": "CI Key", "read_only": True},
            {"id": 2, "title": "Deploy Key", "read_only": True},
        ]
        result = sa.check_deploy_keys("org/repo")
        assert result['total_keys'] == 2
        assert result['write_keys'] == 0
    
    @patch('security_assessment.run_gh_command')
    def test_write_access_keys_flagged(self, mock_cmd):
        mock_cmd.return_value = [
            {"id": 1, "title": "CI Key", "read_only": True},
            {"id": 2, "title": "Admin Key", "read_only": False},
            {"id": 3, "title": "Deploy Key", "read_only": False},
        ]
        result = sa.check_deploy_keys("org/repo")
        assert result['total_keys'] == 3
        assert result['write_keys'] == 2
    
    @patch('security_assessment.run_gh_command')
    def test_keys_not_accessible(self, mock_cmd):
        mock_cmd.return_value = None
        result = sa.check_deploy_keys("org/repo")
        assert result['total_keys'] == 0
        assert 'Not accessible' in result['error']


class TestCheckWebhooks:
    """Tests for webhook security audit."""
    
    @patch('security_assessment.run_gh_command')
    def test_no_webhooks(self, mock_cmd):
        mock_cmd.return_value = []
        result = sa.check_webhooks("org/repo")
        assert result['total_hooks'] == 0
        assert result['insecure_hooks'] == 0
    
    @patch('security_assessment.run_gh_command')
    def test_secure_webhooks(self, mock_cmd):
        mock_cmd.return_value = [
            {"active": True, "config": {"url": "https://example.com/hook", "insecure_ssl": "0", "secret": "abc123"}},
            {"active": True, "config": {"url": "https://ci.example.com/hook", "insecure_ssl": "0", "secret": "def456"}},
        ]
        result = sa.check_webhooks("org/repo")
        assert result['total_hooks'] == 2
        assert result['insecure_hooks'] == 0
    
    @patch('security_assessment.run_gh_command')
    def test_insecure_ssl_flagged(self, mock_cmd):
        mock_cmd.return_value = [
            {"active": True, "config": {"url": "https://example.com/hook", "insecure_ssl": "1", "secret": "abc"}},
        ]
        result = sa.check_webhooks("org/repo")
        assert result['total_hooks'] == 1
        assert result['insecure_hooks'] == 1
    
    @patch('security_assessment.run_gh_command')
    def test_non_https_flagged(self, mock_cmd):
        mock_cmd.return_value = [
            {"active": True, "config": {"url": "http://example.com/hook", "insecure_ssl": "0"}},
        ]
        result = sa.check_webhooks("org/repo")
        assert result['total_hooks'] == 1
        assert result['insecure_hooks'] == 1
    
    @patch('security_assessment.run_gh_command')
    def test_webhooks_not_accessible(self, mock_cmd):
        mock_cmd.return_value = None
        result = sa.check_webhooks("org/repo")
        assert result['total_hooks'] == 0
        assert 'Not accessible' in result['error']
