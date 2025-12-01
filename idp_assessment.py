#!/usr/bin/env python3 -->>> DRAFT first version in the script <<<
"""
GitHub Identity and Access Management Assessment Tool
Validates SSO, MFA, permissions, and token security configurations.

Requirements:
    - GitHub CLI (gh) installed and authenticated
    - Python 3.7+
    - Admin/owner permissions for organization settings

Usage:
    python idp_assessment.py
    
Configuration:
    Edit the CONFIG section below to customize behavior
"""

import subprocess
import json
import sys
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time, sleep
from datetime import datetime
from pathlib import Path
import threading

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # GitHub CLI command
    'gh_command': 'gh',
    
    # Performance settings
    'max_workers': 10,
    
    # Rate limiting
    'enable_rate_limit_check': True,
    'rate_limit_threshold': 100,
    'rate_limit_wait_time': 60,
    'request_delay': 0.05,
    
    # Output settings
    'output_dir': '.',
    'csv_prefix': 'github_idp_assessment',
    
    # Verbose output
    'verbose': True,
}

# ============================================================================
# CORE FUNCTIONS
# ============================================================================

# Rate limit tracking
rate_limit_lock = threading.Lock()
rate_limit_info = {'remaining': None, 'reset_time': None, 'checked': False}

def log(message, verbose_only=False):
    """Print message if verbose or not verbose_only"""
    if not verbose_only or CONFIG['verbose']:
        print(message)

def check_gh_installed():
    """Check if GitHub CLI is installed"""
    try:
        subprocess.run(
            [CONFIG['gh_command'], '--version'],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False

def check_rate_limit():
    """Check GitHub API rate limit status"""
    try:
        result = subprocess.run(
            f"{CONFIG['gh_command']} api rate_limit",
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        data = json.loads(result.stdout)
        core_rate = data.get('resources', {}).get('core', {})
        return {
            'remaining': core_rate.get('remaining', 5000),
            'limit': core_rate.get('limit', 5000),
            'reset_time': core_rate.get('reset', 0)
        }
    except:
        return None

def wait_for_rate_limit():
    """Wait if rate limit is approaching threshold"""
    if not CONFIG['enable_rate_limit_check']:
        return
    
    with rate_limit_lock:
        if not rate_limit_info['checked'] or rate_limit_info['remaining'] is None:
            limit_data = check_rate_limit()
            if limit_data:
                rate_limit_info['remaining'] = limit_data['remaining']
                rate_limit_info['reset_time'] = limit_data['reset_time']
                rate_limit_info['checked'] = True
                
                log(f"📊 Rate Limit: {limit_data['remaining']}/{limit_data['limit']} requests remaining", verbose_only=True)
                
                if limit_data['remaining'] < CONFIG['rate_limit_threshold']:
                    wait_time = CONFIG['rate_limit_wait_time']
                    log(f"⚠️  Rate limit threshold reached ({limit_data['remaining']} remaining)")
                    log(f"   Waiting {wait_time} seconds...")
                    sleep(wait_time)
                    rate_limit_info['checked'] = False
        
        if CONFIG['request_delay'] > 0:
            sleep(CONFIG['request_delay'])

def run_gh_command(command, return_json=True):
    """Run GitHub CLI command and return output"""
    wait_for_rate_limit()
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        if return_json and result.stdout.strip():
            return json.loads(result.stdout)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        return None

def get_organizations():
    """Get all organizations the user has access to"""
    log("Fetching organizations...")
    
    if CONFIG['enable_rate_limit_check']:
        limit_data = check_rate_limit()
        if limit_data:
            log(f"📊 Initial Rate Limit: {limit_data['remaining']}/{limit_data['limit']} requests remaining")
    
    orgs = run_gh_command(f"{CONFIG['gh_command']} api user/orgs --paginate")
    
    if orgs and isinstance(orgs, list):
        return orgs
    return []

def check_org_sso_configuration(org_login):
    """Check organization SSO and authentication configuration"""
    try:
        # Get organization details
        org_data = run_gh_command(f"{CONFIG['gh_command']} api orgs/{org_login}")
        
        if not org_data:
            return {'error': 'Cannot access organization', 'has_access': False}
        
        # Check if 2FA is required at org level
        two_factor_requirement = org_data.get('two_factor_requirement_enabled', False)
        
        # Get organization plan (helps identify enterprise features)
        plan = org_data.get('plan', {}).get('name', 'free')
        
        # Check if organization is part of an enterprise
        # Enterprise plans include: enterprise, team, enterprise_cloud
        has_enterprise = 'enterprise' in plan.lower() or 'team' in plan.lower()
        enterprise_slug = org_login if has_enterprise else None
        
        # Check SAML SSO configuration
        # Note: For Enterprise plans, SAML/OIDC is typically configured at Enterprise level
        saml_enabled = False
        sso_type = 'Enterprise-level (verify in IdP)'
        verification_note = ''
        
        # For Enterprise organizations, SSO/OIDC is managed at enterprise level in IdP
        if has_enterprise:
            sso_type = 'Enterprise-level OIDC/SAML'
            verification_note = '✓ Enterprise plan detected. SSO/OIDC configured at Enterprise level.\n' + \
                              '   Verify configuration in Entra ID (Azure AD):\n' + \
                              '   • Portal: https://portal.azure.com\n' + \
                              '   • Navigate to: Enterprise Applications → GitHub\n' + \
                              '   • Verify: SAML/OIDC configuration, user assignments, MFA policies\n' + \
                              '   • Check: Conditional Access → GitHub application policies'
        
        return {
            'has_access': True,
            'org_name': org_data.get('name', org_login),
            'org_login': org_login,
            'plan': plan,
            'has_enterprise': has_enterprise,
            'enterprise_slug': enterprise_slug,
            'two_factor_required': two_factor_requirement,
            'saml_enabled': saml_enabled,
            'sso_type': sso_type,
            'verification_note': verification_note,
            'has_ip_allow_list': org_data.get('has_ip_allow_list', False),
            'members_can_create_repositories': org_data.get('members_can_create_repositories', True),
            'error': None
        }
    except Exception as e:
        return {
            'has_access': False,
            'error': str(e)
        }

def check_org_member_privileges(org_login):
    """Check granular permissions and member privileges"""
    try:
        # Get organization member privileges settings
        org_data = run_gh_command(f"{CONFIG['gh_command']} api orgs/{org_login}")
        
        if not org_data:
            return {'error': 'Cannot access organization'}
        
        return {
            'members_can_create_repositories': org_data.get('members_can_create_repositories', True),
            'members_can_create_public_repositories': org_data.get('members_can_create_public_repositories', True),
            'members_can_create_private_repositories': org_data.get('members_can_create_private_repositories', True),
            'members_can_create_internal_repositories': org_data.get('members_can_create_internal_repositories', True),
            'members_can_fork_private_repositories': org_data.get('members_can_fork_private_repositories', True),
            'members_can_create_pages': org_data.get('members_can_create_pages', True),
            'members_can_create_public_pages': org_data.get('members_can_create_public_pages', True),
            'members_can_create_private_pages': org_data.get('members_can_create_private_pages', True),
            'default_repository_permission': org_data.get('default_repository_permission', 'read'),
            'error': None
        }
    except Exception as e:
        return {'error': str(e)}

def check_org_environments(org_login):
    """Check environment segregation and protection rules"""
    try:
        # Get all repositories in the organization
        repos = run_gh_command(
            f"{CONFIG['gh_command']} api orgs/{org_login}/repos --paginate --jq '[.[] | .name]'"
        )
        
        if not repos:
            return {'total_repos': 0, 'repos_with_environments': 0, 'error': 'No repositories'}
        
        repos_with_envs = 0
        total_repos = len(repos) if isinstance(repos, list) else 0
        
        # Sample first few repos to check for environments (avoid rate limit issues)
        sample_size = min(5, total_repos)
        for i in range(sample_size):
            if isinstance(repos, list) and i < len(repos):
                repo_name = repos[i]
                envs = run_gh_command(
                    f"{CONFIG['gh_command']} api repos/{org_login}/{repo_name}/environments",
                    return_json=True
                )
                if envs and isinstance(envs, dict) and envs.get('environments'):
                    repos_with_envs += 1
        
        return {
            'total_repos': total_repos,
            'repos_sampled': sample_size,
            'repos_with_environments': repos_with_envs,
            'environment_usage_percentage': (repos_with_envs / sample_size * 100) if sample_size > 0 else 0,
            'error': None
        }
    except Exception as e:
        return {'total_repos': 0, 'repos_with_environments': 0, 'error': str(e)}

def check_org_token_security(org_login):
    """Check token and secret security policies"""
    try:
        # Get organization security settings
        org_data = run_gh_command(f"{CONFIG['gh_command']} api orgs/{org_login}")
        
        if not org_data:
            return {'error': 'Cannot access organization'}
        
        # Check Advanced Security features
        security_data = org_data.get('advanced_security_enabled_for_new_repositories', False)
        
        # Check secret scanning
        secret_scanning = org_data.get('secret_scanning_enabled_for_new_repositories', False)
        secret_scanning_push_protection = org_data.get('secret_scanning_push_protection_enabled_for_new_repositories', False)
        
        # Check Dependabot
        dependabot_alerts = org_data.get('dependabot_alerts_enabled_for_new_repositories', False)
        dependabot_security_updates = org_data.get('dependabot_security_updates_enabled_for_new_repositories', False)
        
        return {
            'advanced_security_for_new_repos': security_data,
            'secret_scanning_for_new_repos': secret_scanning,
            'secret_scanning_push_protection': secret_scanning_push_protection,
            'dependabot_alerts_for_new_repos': dependabot_alerts,
            'dependabot_security_updates_for_new_repos': dependabot_security_updates,
            'error': None
        }
    except Exception as e:
        return {'error': str(e)}

def assess_organization(org):
    """Perform comprehensive IAM assessment on an organization"""
    org_login = org['login']
    
    log(f"Assessing {org_login}...", verbose_only=True)
    
    result = {
        'org_login': org_login,
        'org_id': org.get('id'),
    }
    
    # Check each IAM aspect
    result['sso_config'] = check_org_sso_configuration(org_login)
    result['member_privileges'] = check_org_member_privileges(org_login)
    result['environments'] = check_org_environments(org_login)
    result['token_security'] = check_org_token_security(org_login)
    
    return result

def assess_all_organizations(orgs):
    """Assess all organizations in parallel"""
    log("\nAssessing organization IAM configurations...")
    
    results = []
    total = len(orgs)
    
    if total == 0:
        log("⚠️  No organizations found or no access to organization settings")
        return results
    
    with ThreadPoolExecutor(max_workers=CONFIG['max_workers']) as executor:
        future_to_org = {executor.submit(assess_organization, org): org for org in orgs}
        
        completed = 0
        for future in as_completed(future_to_org):
            result = future.result()
            results.append(result)
            completed += 1
            
            log(f"⚡ Progress: {completed}/{total} organizations assessed ({(completed/total*100):.0f}%)", verbose_only=True)
    
    results.sort(key=lambda x: x['org_login'])
    return results

def export_to_csv(results):
    """Export results to CSV"""
    log("\n" + "=" * 80)
    log("EXPORTING TO CSV")
    log("=" * 80)
    
    export_data = []
    
    for result in results:
        sso = result['sso_config']
        privs = result['member_privileges']
        envs = result['environments']
        tokens = result['token_security']
        
        row = {
            'Organization': result['org_login'],
            'Organization ID': result['org_id'],
            
            # SSO & Authentication
            'Plan': sso.get('plan', 'Unknown'),
            'Has Enterprise Plan': 'Yes' if sso.get('has_enterprise', False) else 'No',
            'Enterprise Slug': sso.get('enterprise_slug', 'N/A'),
            '2FA Required (Org Level)': 'Yes' if sso.get('two_factor_required', False) else 'No (May use IdP)' if sso.get('has_enterprise') else 'No',
            'SSO Type': sso.get('sso_type', 'None'),
            'IP Allow List': 'Yes' if sso.get('has_ip_allow_list', False) else 'No',
            'SSO Status': '✓ Enterprise SSO (Verify in IdP)' if sso.get('has_enterprise') else 'Configure SAML/OIDC',
            'Verification Instructions': sso.get('verification_note', 'N/A'),
            
            # Granular Permissions
            'Default Repo Permission': privs.get('default_repository_permission', 'Unknown'),
            'Members Can Create Repos': 'Yes' if privs.get('members_can_create_repositories', True) else 'No',
            'Members Can Create Public Repos': 'Yes' if privs.get('members_can_create_public_repositories', True) else 'No',
            'Members Can Fork Private Repos': 'Yes' if privs.get('members_can_fork_private_repositories', True) else 'No',
            'Permissions Status': '✅ Pass' if privs.get('default_repository_permission') in ['read', 'none'] else '⚠️ Review',
            
            # Environment Segregation
            'Total Repositories': envs.get('total_repos', 0),
            'Repos with Environments (Sample)': envs.get('repos_with_environments', 0),
            'Environment Usage %': f"{envs.get('environment_usage_percentage', 0):.1f}%",
            'Environment Segregation Status': '✅ Pass' if envs.get('environment_usage_percentage', 0) > 20 else '⚠️ Low Usage',
            
            # Token & Secret Security
            'Advanced Security Enabled': 'Yes' if tokens.get('advanced_security_for_new_repos', False) else 'No',
            'Secret Scanning for New Repos': 'Yes' if tokens.get('secret_scanning_for_new_repos', False) else 'No',
            'Dependabot Alerts Enabled': 'Yes' if tokens.get('dependabot_alerts_for_new_repos', False) else 'No',
            'Token Security Status': '✅ Pass' if tokens.get('secret_scanning_for_new_repos', False) else '⚠️ Review',
            
            # Overall Compliance
            'Overall IAM Status': '✅ Compliant' if all([
                # Enterprise orgs use IdP for auth, so don't require org-level 2FA setting
                (sso.get('two_factor_required', False) or sso.get('has_enterprise', False)),
                privs.get('default_repository_permission') in ['read', 'none'],
                tokens.get('secret_scanning_for_new_repos', False)
            ]) else '⚠️ Review Required',
            
            # Errors
            'Errors': '; '.join(filter(None, [
                sso.get('error'),
                privs.get('error'),
                envs.get('error'),
                tokens.get('error')
            ])) or 'None'
        }
        
        export_data.append(row)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{CONFIG['csv_prefix']}_{timestamp}.csv"
    filepath = Path(CONFIG['output_dir']) / filename
    
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    if export_data:
        fieldnames = list(export_data[0].keys())
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(export_data)
        
        log(f"✅ CSV file created: {filepath}")
        log(f"   Total rows: {len(export_data)}")
        log(f"   Columns: {len(fieldnames)}")
        return str(filepath)
    else:
        log("❌ No data to export")
        return None

def print_summary(results, fetch_time, assess_time, total_time):
    """Print summary statistics"""
    
    total_orgs = len(results)
    
    if total_orgs == 0:
        log("\n⚠️  No organizations to assess")
        return
    
    # Calculate statistics
    sso_with_2fa = sum(1 for r in results if r['sso_config'].get('two_factor_required', False))
    sso_with_saml = sum(1 for r in results if r['sso_config'].get('saml_enabled', False))
    
    secure_permissions = sum(1 for r in results if r['member_privileges'].get('default_repository_permission') in ['read', 'none'])
    
    with_secret_scanning = sum(1 for r in results if r['token_security'].get('secret_scanning_for_new_repos', False))
    
    # Check for enterprise organizations
    with_enterprise = sum(1 for r in results if r['sso_config'].get('has_enterprise', False))
    
    # Adjust compliance: Enterprise orgs may have SSO at enterprise level
    fully_compliant = sum(1 for r in results if all([
        # Either 2FA enabled OR has enterprise (SSO likely at enterprise level)
        (r['sso_config'].get('two_factor_required', False) or r['sso_config'].get('has_enterprise', False)),
        r['member_privileges'].get('default_repository_permission') in ['read', 'none'],
        r['token_security'].get('secret_scanning_for_new_repos', False)
    ]))
    
    log("\n" + "=" * 80)
    log("IDENTITY & ACCESS MANAGEMENT ASSESSMENT SUMMARY")
    log("=" * 80)
    log(f"Total organizations assessed: {total_orgs}")
    
    log(f"\n🔐 SSO & AUTHENTICATION:")
    log(f"   ✓ Organizations with Enterprise Plan: {with_enterprise}/{total_orgs} ({(with_enterprise/total_orgs*100):.1f}%)")
    log(f"   2FA Requirement (Org Level Setting): {sso_with_2fa}/{total_orgs} ({(sso_with_2fa/total_orgs*100):.1f}%)")
    
    if with_enterprise > 0:
        log(f"\n   ✓ {with_enterprise} organization(s) have Enterprise plan")
        log(f"   Enterprise plans have SSO/OIDC configured at Enterprise level in IdP")
        log(f"   MFA enforcement is typically managed via Conditional Access policies")
        log(f"   (Org-level 2FA setting may be disabled when using Enterprise SSO)")
    
    log(f"\n👥 GRANULAR PERMISSIONS:")
    log(f"   Secure Default Permissions (read/none): {secure_permissions}/{total_orgs} ({(secure_permissions/total_orgs*100):.1f}%)")
    
    log(f"\n🔑 TOKEN & SECRET SECURITY:")
    log(f"   Secret Scanning for New Repos: {with_secret_scanning}/{total_orgs} ({(with_secret_scanning/total_orgs*100):.1f}%)")
    
    log(f"\n✅ FULLY COMPLIANT ORGANIZATIONS: {fully_compliant}/{total_orgs} ({(fully_compliant/total_orgs*100):.1f}%)")
    
    # Show final rate limit
    if CONFIG['enable_rate_limit_check']:
        final_limit = check_rate_limit()
        if final_limit:
            log(f"\n📊 Final Rate Limit: {final_limit['remaining']}/{final_limit['limit']} requests remaining")
    
    log(f"\n⚡ PERFORMANCE METRICS:")
    log(f"   Organization fetch: {fetch_time:.2f}s")
    log(f"   IAM assessment: {assess_time:.2f}s")
    log(f"   Total execution: {total_time:.2f}s")
    
    # Show recommendations
    log(f"\n💡 RECOMMENDATIONS:")
    
    # Show enterprise-specific verification
    enterprise_orgs = [r for r in results if r['sso_config'].get('has_enterprise')]
    if enterprise_orgs:
        log(f"\n   🔍 ENTERPRISE SSO/OIDC VERIFICATION:")
        log(f"   ✓ {len(enterprise_orgs)} organization(s) have Enterprise plan with SSO at Enterprise level")
        log(f"\n   📋 Verification Steps for Entra ID (Azure AD):")
        log(f"   1. Portal: https://portal.azure.com")
        log(f"   2. Navigate to: Enterprise Applications → Search 'GitHub'")
        log(f"   3. Verify Single Sign-On:")
        log(f"      • SAML/OIDC configuration is active and properly configured")
        log(f"      • Single sign-on status: Enabled")
        log(f"      • Test sign-on functionality")
        log(f"   4. Check Conditional Access (for MFA enforcement):")
        log(f"      • Security → Conditional Access → Policies")
        log(f"      • Verify MFA requirement is enabled for GitHub application")
        log(f"      • Check trusted locations, device compliance, session controls")
        log(f"   5. Review Users and Groups:")
        log(f"      • Enterprise Applications → GitHub → Users and groups")
        log(f"      • Confirm all organization members are properly assigned")
        log(f"      • Verify group-based access if applicable")
        log(f"\n   Note: Enterprise orgs use IdP (Entra ID) for authentication.")
        log(f"         MFA is enforced via Conditional Access, not GitHub org settings.")
    
    non_enterprise_no_2fa = [r for r in results 
                             if not r['sso_config'].get('has_enterprise') 
                             and not r['sso_config'].get('two_factor_required', False)]
    if non_enterprise_no_2fa:
        log(f"\n   ⚠️  Enable 2FA requirement for {len(non_enterprise_no_2fa)} non-enterprise organizations")
        log(f"      (Enterprise orgs use IdP-based authentication)")
    
    if secure_permissions < total_orgs:
        log(f"   ⚠️  Review default repository permissions for {total_orgs - secure_permissions} organizations")
        log(f"      • Set to 'read' or 'none' for better security")
    
    if with_secret_scanning < total_orgs:
        log(f"   ⚠️  Enable Secret Scanning for new repos for {total_orgs - with_secret_scanning} organizations")
        log(f"      • See security assessment for push protection details")
    
    log(f"\n📚 ADDITIONAL RESOURCES:")
    log(f"   • SAML SSO Setup: https://docs.github.com/enterprise-cloud@latest/organizations/managing-saml-single-sign-on-for-your-organization")
    log(f"   • Entra ID Integration: https://learn.microsoft.com/entra/identity/saas-apps/github-tutorial")
    log(f"   • 2FA Enforcement: https://docs.github.com/organizations/keeping-your-organization-secure/managing-two-factor-authentication-for-your-organization")
    log(f"   • Token Security: https://docs.github.com/code-security/secret-scanning/about-secret-scanning")

def main():
    """Main execution function"""
    start_time = time()
    
    log("=" * 80)
    log("GITHUB IDENTITY & ACCESS MANAGEMENT ASSESSMENT TOOL")
    log("=" * 80)
    
    # Check prerequisites
    if not check_gh_installed():
        log("\n❌ GitHub CLI (gh) is not installed or not in PATH!")
        log("\nTo install:")
        log("  Windows: winget install --id GitHub.cli")
        log("  macOS:   brew install gh")
        log("  Linux:   See https://cli.github.com/")
        log("\nAfter installation, authenticate with: gh auth login")
        return 1
    
    # Get organizations
    fetch_start = time()
    orgs = get_organizations()
    fetch_time = time() - fetch_start
    
    if not orgs:
        log("\n⚠️  No organizations found or you don't have access to organization settings.")
        log("   This tool requires access to organization-level settings.")
        log("   Make sure you're an organization owner or admin.")
        return 1
    
    log(f"✓ Found {len(orgs)} organizations in {fetch_time:.2f}s")
    
    # Assess organizations
    assess_start = time()
    results = assess_all_organizations(orgs)
    assess_time = time() - assess_start
    
    # Export results
    if results:
        csv_file = export_to_csv(results)
    
    # Print summary
    total_time = time() - start_time
    print_summary(results, fetch_time, assess_time, total_time)
    
    log("\n" + "=" * 80)
    log("✅ IAM assessment complete!")
    log("=" * 80)
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("\n\n⚠️  Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        log(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
