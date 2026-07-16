"""Tests for idp_assessment.py new checks (Org Governance)."""
import json
from unittest.mock import patch
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import idp_assessment as idp


class TestCheckOrgRulesets:
    """Tests for organization-level rulesets check."""
    
    @patch('idp_assessment.run_gh_command')
    def test_no_rulesets(self, mock_cmd):
        mock_cmd.return_value = []
        result = idp.check_org_rulesets("myorg")
        assert result['total_rulesets'] == 0
        assert result['active_rulesets'] == 0
        assert result['has_pr_requirement'] is False
    
    @patch('idp_assessment.run_gh_command')
    def test_active_rulesets_with_pr_requirement(self, mock_cmd):
        mock_cmd.side_effect = [
            [{"id": 1, "name": "Protect main", "enforcement": "active"}],
            {"id": 1, "rules": [{"type": "required_pull_request"}]}
        ]
        result = idp.check_org_rulesets("myorg")
        assert result['total_rulesets'] == 1
        assert result['active_rulesets'] == 1
        assert result['has_pr_requirement'] is True
    
    @patch('idp_assessment.run_gh_command')
    def test_disabled_rulesets(self, mock_cmd):
        mock_cmd.side_effect = [
            [{"id": 1, "name": "Draft", "enforcement": "disabled"}],
        ]
        result = idp.check_org_rulesets("myorg")
        assert result['total_rulesets'] == 1
        assert result['active_rulesets'] == 0
        assert result['has_pr_requirement'] is False
    
    @patch('idp_assessment.run_gh_command')
    def test_rulesets_not_accessible(self, mock_cmd):
        mock_cmd.return_value = None
        result = idp.check_org_rulesets("myorg")
        assert result['total_rulesets'] == 0


class TestCheckOutsideCollaborators:
    """Tests for outside collaborators audit."""
    
    @patch('idp_assessment.run_gh_command')
    def test_no_outside_collaborators(self, mock_cmd):
        mock_cmd.side_effect = [[], []]
        result = idp.check_outside_collaborators("myorg")
        assert result['total'] == 0
        assert result['without_2fa'] == 0
    
    @patch('idp_assessment.run_gh_command')
    def test_collaborators_all_with_2fa(self, mock_cmd):
        mock_cmd.side_effect = [
            [{"login": "ext1"}, {"login": "ext2"}],
            []  # none without 2FA
        ]
        result = idp.check_outside_collaborators("myorg")
        assert result['total'] == 2
        assert result['without_2fa'] == 0
    
    @patch('idp_assessment.run_gh_command')
    def test_collaborators_without_2fa(self, mock_cmd):
        mock_cmd.side_effect = [
            [{"login": "ext1"}, {"login": "ext2"}, {"login": "ext3"}],
            [{"login": "ext2"}]  # one without 2FA
        ]
        result = idp.check_outside_collaborators("myorg")
        assert result['total'] == 3
        assert result['without_2fa'] == 1
    
    @patch('idp_assessment.run_gh_command')
    def test_not_accessible(self, mock_cmd):
        mock_cmd.return_value = None
        result = idp.check_outside_collaborators("myorg")
        assert result['total'] == 0
        assert 'Not accessible' in result['error']


class TestCheckOrgActionsPermissions:
    """Tests for organization Actions permissions."""
    
    @patch('idp_assessment.run_gh_command')
    def test_secure_actions_config(self, mock_cmd):
        mock_cmd.side_effect = [
            {"enabled_repositories": "all", "allowed_actions": "selected"},
            {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False},
        ]
        result = idp.check_org_actions_permissions("myorg")
        assert result['allowed_actions'] == 'selected'
        assert result['default_workflow_permissions'] == 'read'
        assert result['can_approve_prs'] is False
    
    @patch('idp_assessment.run_gh_command')
    def test_permissive_actions(self, mock_cmd):
        mock_cmd.side_effect = [
            {"enabled_repositories": "all", "allowed_actions": "all"},
            {"default_workflow_permissions": "write", "can_approve_pull_request_reviews": True},
        ]
        result = idp.check_org_actions_permissions("myorg")
        assert result['allowed_actions'] == 'all'
        assert result['default_workflow_permissions'] == 'write'
        assert result['can_approve_prs'] is True
    
    @patch('idp_assessment.run_gh_command')
    def test_not_accessible(self, mock_cmd):
        mock_cmd.return_value = None
        result = idp.check_org_actions_permissions("myorg")
        assert 'error' in result


class TestCheckCodeSecurityConfig:
    """Tests for code security configurations."""
    
    @patch('idp_assessment.run_gh_command')
    def test_has_enforced_config(self, mock_cmd):
        mock_cmd.return_value = [
            {"name": "High Security", "enforcement": "enforced"},
            {"name": "Standard", "enforcement": "unenforced"},
        ]
        result = idp.check_code_security_config("myorg")
        assert result['has_config'] is True
        assert result['total_configs'] == 2
        assert result['has_enforced'] is True
    
    @patch('idp_assessment.run_gh_command')
    def test_no_enforced_config(self, mock_cmd):
        mock_cmd.return_value = [
            {"name": "Draft", "enforcement": "unenforced"},
        ]
        result = idp.check_code_security_config("myorg")
        assert result['has_config'] is True
        assert result['has_enforced'] is False
    
    @patch('idp_assessment.run_gh_command')
    def test_no_configs(self, mock_cmd):
        mock_cmd.return_value = []
        result = idp.check_code_security_config("myorg")
        assert result['has_config'] is False
        assert result['total_configs'] == 0


class TestCheckCopilotSettings:
    """Tests for Copilot settings including premium budget."""
    
    @patch('idp_assessment.run_gh_command')
    def test_copilot_with_budget(self, mock_cmd):
        mock_cmd.side_effect = [
            {  # billing response
                "seat_breakdown": {"total": 50, "active_this_cycle": 45, "inactive_this_cycle": 5},
                "seat_management_setting": "assign_selected",
                "public_code_suggestions": "block",
            },
            {"premium_requests_budget_monthly_limit": 1000},  # policies response
        ]
        result = idp.check_copilot_settings("myorg")
        assert result['enabled'] is True
        assert result['total_seats'] == 50
        assert result['public_code_suggestions'] == 'block'
        assert result['has_premium_budget'] is True
        assert result['premium_budget_limit'] == 1000
    
    @patch('idp_assessment.run_gh_command')
    def test_copilot_without_budget(self, mock_cmd):
        mock_cmd.side_effect = [
            {  # billing response
                "seat_breakdown": {"total": 10, "active_this_cycle": 8, "inactive_this_cycle": 2},
                "seat_management_setting": "assign_all",
                "public_code_suggestions": "allow",
            },
            None,  # policies not accessible
        ]
        result = idp.check_copilot_settings("myorg")
        assert result['enabled'] is True
        assert result['public_code_suggestions'] == 'allow'
        assert result['has_premium_budget'] is False
    
    @patch('idp_assessment.run_gh_command')
    def test_copilot_not_enabled(self, mock_cmd):
        mock_cmd.return_value = None
        result = idp.check_copilot_settings("myorg")
        assert result['enabled'] is False


class TestCheckPatPolicies:
    """Tests for PAT policies check."""
    
    @patch('idp_assessment.run_gh_command')
    def test_pending_requests(self, mock_cmd):
        mock_cmd.side_effect = [
            {"login": "myorg"},  # org data
            [{"id": 1}, {"id": 2}],  # pending requests
        ]
        result = idp.check_pat_policies("myorg")
        assert result['pending_pat_requests'] == 2
    
    @patch('idp_assessment.run_gh_command')
    def test_no_pending_requests(self, mock_cmd):
        mock_cmd.side_effect = [
            {"login": "myorg"},
            [],
        ]
        result = idp.check_pat_policies("myorg")
        assert result['pending_pat_requests'] == 0
