#!/usr/bin/env python3 >>>DRAFT first version in the script <<<
"""
GitHub Security Assessment Tool
Checks repositories for security controls and compliance.

Requirements:
    - GitHub CLI (gh) installed and authenticated
    - Python 3.7+
    - Appropriate permissions to access security settings

Usage:
    python security_assessment.py
    
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
    'max_workers_fetch': 10,
    'max_workers_check': 15,
    
    # Rate limiting
    'enable_rate_limit_check': True,
    'rate_limit_threshold': 100,
    'rate_limit_wait_time': 60,
    'request_delay': 0.05,
    
    # Output settings
    'output_dir': '.',
    'csv_prefix': 'github_security_assessment',
    
    # Personal account identifier (used to detect personal vs org repos)
    # Leave empty to auto-detect from GitHub CLI authenticated user
    'personal_account': '',
    
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

def fetch_org_security_settings(org_login):
    """Fetch organization-level security settings for new repositories"""
    try:
        org_data = run_gh_command(f"{CONFIG['gh_command']} api orgs/{org_login}")
        
        if not org_data:
            return None
        
        return {
            'org_login': org_login,
            'advanced_security_for_new_repos': org_data.get('advanced_security_enabled_for_new_repositories', False),
            'secret_scanning_for_new_repos': org_data.get('secret_scanning_enabled_for_new_repositories', False),
            'secret_scanning_push_protection_for_new_repos': org_data.get('secret_scanning_push_protection_enabled_for_new_repositories', False),
            'dependabot_alerts_for_new_repos': org_data.get('dependabot_alerts_enabled_for_new_repositories', False),
            'dependabot_security_updates_for_new_repos': org_data.get('dependabot_security_updates_enabled_for_new_repositories', False),
        }
    except Exception as e:
        return None

def fetch_repositories():
    """Fetch all accessible repositories and organization settings"""
    log("Fetching repositories and organization settings...")
    
    # Auto-detect personal account if not set
    if not CONFIG['personal_account']:
        user_info = run_gh_command(f"{CONFIG['gh_command']} api user --jq '.login'", return_json=False)
        if user_info:
            CONFIG['personal_account'] = user_info.strip('"')
            log(f"Detected personal account: {CONFIG['personal_account']}", verbose_only=True)
    
    if CONFIG['enable_rate_limit_check']:
        limit_data = check_rate_limit()
        if limit_data:
            log(f"📊 Initial Rate Limit: {limit_data['remaining']}/{limit_data['limit']} requests remaining")
    
    all_repos = []
    org_settings = {}
    
    with ThreadPoolExecutor(max_workers=CONFIG['max_workers_fetch']) as executor:
        futures = []
        
        # Fetch user repos
        futures.append(executor.submit(
            run_gh_command,
            f"{CONFIG['gh_command']} repo list --json nameWithOwner,name,owner,isPrivate --limit 1000"
        ))
        
        # Get organizations
        orgs_future = executor.submit(
            run_gh_command,
            f"{CONFIG['gh_command']} api user/orgs --paginate"
        )
        orgs_data = orgs_future.result()
        
        if orgs_data:
            for org in orgs_data:
                org_login = org['login']
                futures.append(executor.submit(
                    run_gh_command,
                    f"{CONFIG['gh_command']} repo list {org_login} --json nameWithOwner,name,owner,isPrivate --limit 1000"
                ))
                # Fetch organization security settings
                futures.append(executor.submit(
                    fetch_org_security_settings,
                    org_login
                ))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                if isinstance(result, list):
                    all_repos.extend(result)
                elif isinstance(result, dict) and 'org_login' in result:
                    # Organization settings
                    org_settings[result['org_login']] = result
    
    # Remove duplicates
    seen = set()
    unique_repos = []
    for repo in all_repos:
        if repo['nameWithOwner'] not in seen:
            seen.add(repo['nameWithOwner'])
            unique_repos.append(repo)
    
    return unique_repos, org_settings

def check_code_scanning(repo_name):
    """Check if code scanning is enabled and get alerts"""
    try:
        # Check for code scanning alerts
        alerts = run_gh_command(
            f"{CONFIG['gh_command']} api repos/{repo_name}/code-scanning/alerts --jq 'length'"
        )
        
        if alerts is None:
            return {'enabled': False, 'critical_alerts': 0, 'error': 'Not accessible or not enabled'}
        
        # Get critical alerts
        critical = run_gh_command(
            f'{CONFIG["gh_command"]} api repos/{repo_name}/code-scanning/alerts --jq \'[.[] | select(.state == "open" and .rule.severity == "error")] | length\''
        )
        
        critical_count = int(critical) if critical and critical.isdigit() else 0
        
        return {
            'enabled': True,
            'critical_alerts': critical_count,
            'error': None
        }
    except Exception as e:
        return {'enabled': False, 'critical_alerts': 0, 'error': str(e)}

def check_secret_scanning(repo_name):
    """Check if secret scanning is active"""
    try:
        # Get repository settings
        repo_data = run_gh_command(
            f"{CONFIG['gh_command']} api repos/{repo_name}"
        )
        
        if repo_data is None:
            return {'enabled': False, 'error': 'Not accessible'}
        
        # Check if secret scanning is enabled
        security_data = repo_data.get('security_and_analysis', {})
        secret_scanning = security_data.get('secret_scanning', {})
        secret_scanning_push_protection = security_data.get('secret_scanning_push_protection', {})
        
        enabled = secret_scanning.get('status') == 'enabled'
        push_protection = secret_scanning_push_protection.get('status') == 'enabled'
        
        # Get open alerts count
        alerts = run_gh_command(
            f'{CONFIG["gh_command"]} api repos/{repo_name}/secret-scanning/alerts --jq \'[.[] | select(.state == "open")] | length\''
        )
        
        open_alerts = int(alerts) if alerts and alerts.isdigit() else 0
        
        return {
            'enabled': enabled,
            'push_protection': push_protection,
            'open_alerts': open_alerts,
            'error': None
        }
    except Exception as e:
        return {'enabled': False, 'push_protection': False, 'open_alerts': 0, 'error': str(e)}

def check_dependabot(repo_name):
    """Check if Dependabot alerts are configured"""
    try:
        # Get repository settings
        repo_data = run_gh_command(
            f"{CONFIG['gh_command']} api repos/{repo_name}"
        )
        
        if repo_data is None:
            return {'enabled': False, 'error': 'Not accessible'}
        
        # Check if Dependabot is enabled
        security_data = repo_data.get('security_and_analysis', {})
        dependabot = security_data.get('dependabot_security_updates', {})
        
        enabled = dependabot.get('status') == 'enabled'
        
        # Get open vulnerability alerts
        alerts = run_gh_command(
            f'{CONFIG["gh_command"]} api repos/{repo_name}/dependabot/alerts --jq \'[.[] | select(.state == "open")] | length\''
        )
        
        open_alerts = int(alerts) if alerts and alerts.isdigit() else 0
        
        # Get critical alerts
        critical = run_gh_command(
            f'{CONFIG["gh_command"]} api repos/{repo_name}/dependabot/alerts --jq \'[.[] | select(.state == "open" and .security_advisory.severity == "critical")] | length\''
        )
        
        critical_alerts = int(critical) if critical and critical.isdigit() else 0
        
        return {
            'enabled': enabled,
            'open_alerts': open_alerts,
            'critical_alerts': critical_alerts,
            'error': None
        }
    except Exception as e:
        return {'enabled': False, 'open_alerts': 0, 'critical_alerts': 0, 'error': str(e)}

def check_branch_protection(repo_name):
    """Check if branch protection rules or rulesets are applied"""
    try:
        # Get default branch
        repo_data = run_gh_command(
            f"{CONFIG['gh_command']} api repos/{repo_name} --jq '.default_branch'"
        )
        
        if not repo_data:
            return {'enabled': False, 'uses_rulesets': False, 'error': 'Cannot get default branch'}
        
        default_branch = repo_data.strip('"')
        
        # Check for repository rulesets (newer approach)
        rulesets = run_gh_command(
            f"{CONFIG['gh_command']} api repos/{repo_name}/rulesets"
        )
        
        has_rulesets = False
        if rulesets and isinstance(rulesets, list) and len(rulesets) > 0:
            has_rulesets = True
        
        # Get branch protection (legacy approach)
        protection = run_gh_command(
            f"{CONFIG['gh_command']} api repos/{repo_name}/branches/{default_branch}/protection"
        )
        
        if protection is None and not has_rulesets:
            return {
                'enabled': False,
                'uses_rulesets': False,
                'requires_reviews': False,
                'requires_status_checks': False,
                'error': 'No protection rules or rulesets configured'
            }
        
        # Parse protection rules or rulesets
        requires_reviews = False
        requires_status_checks = False
        enforces_admins = False
        
        if protection:
            requires_reviews = protection.get('required_pull_request_reviews') is not None
            requires_status_checks = protection.get('required_status_checks') is not None
            enforces_admins = protection.get('enforce_admins', {}).get('enabled', False)
        
        return {
            'enabled': protection is not None or has_rulesets,
            'uses_rulesets': has_rulesets,
            'requires_reviews': requires_reviews,
            'requires_status_checks': requires_status_checks,
            'enforces_admins': enforces_admins,
            'default_branch': default_branch,
            'error': None
        }
    except Exception as e:
        return {
            'enabled': False,
            'uses_rulesets': False,
            'requires_reviews': False,
            'requires_status_checks': False,
            'enforces_admins': False,
            'error': str(e)
        }

def assess_repository_security(repo, org_settings):
    """Perform comprehensive security assessment on a repository"""
    repo_name = repo['nameWithOwner']
    owner = repo_name.split('/')[0]
    
    log(f"Assessing {repo_name}...", verbose_only=True)
    
    result = {
        'repo_name': repo_name,
        'owner': owner,
        'is_private': repo.get('isPrivate', False),
    }
    
    # Get organization settings if this is an org repo
    org_config = org_settings.get(owner, {})
    
    # Check each security control
    result['code_scanning'] = check_code_scanning(repo_name)
    result['secret_scanning'] = check_secret_scanning(repo_name)
    result['dependabot'] = check_dependabot(repo_name)
    result['branch_protection'] = check_branch_protection(repo_name)
    result['org_settings'] = org_config
    
    return result

def assess_all_repositories(repos, org_settings):
    """Assess all repositories in parallel"""
    log("\nAssessing repository security (parallel execution)...")
    
    results = []
    total = len(repos)
    
    with ThreadPoolExecutor(max_workers=CONFIG['max_workers_check']) as executor:
        future_to_repo = {executor.submit(assess_repository_security, repo, org_settings): repo for repo in repos}
        
        completed = 0
        for future in as_completed(future_to_repo):
            result = future.result()
            results.append(result)
            completed += 1
            
            log(f"⚡ Progress: {completed}/{total} repositories assessed ({(completed/total*100):.0f}%)", verbose_only=True)
    
    results.sort(key=lambda x: x['repo_name'])
    return results

def export_to_csv(results):
    """Export results to CSV"""
    log("\n" + "=" * 80)
    log("EXPORTING TO CSV")
    log("=" * 80)
    
    export_data = []
    
    for result in results:
        repo_name = result['repo_name']
        owner = result['owner']
        is_org = owner != CONFIG['personal_account']
        
        code_scan = result['code_scanning']
        secret_scan = result['secret_scanning']
        dependabot = result['dependabot']
        branch_prot = result['branch_protection']
        org_config = result.get('org_settings', {})
        
        # Determine if org has good defaults
        has_org_defaults = bool(org_config)
        secret_scan_default = org_config.get('secret_scanning_for_new_repos', False) if has_org_defaults else 'N/A'
        secret_scan_pp_default = org_config.get('secret_scanning_push_protection_for_new_repos', False) if has_org_defaults else 'N/A'
        dependabot_default = org_config.get('dependabot_alerts_for_new_repos', False) if has_org_defaults else 'N/A'
        
        row = {
            'Repository': repo_name,
            'Owner': owner,
            'Type': 'Organization' if is_org else 'Personal',
            'Is Private': 'Yes' if result['is_private'] else 'No',
            
            # Code Scanning
            'Code Scanning Enabled': 'Yes' if code_scan['enabled'] else 'No',
            'Code Scanning Critical Alerts': code_scan.get('critical_alerts', 0),
            'Code Scanning Status': '✅ Pass' if code_scan['enabled'] and code_scan.get('critical_alerts', 0) == 0 else '❌ Fail',
            
            # Secret Scanning (Actual + Org Default)
            'Secret Scanning Enabled': 'Yes' if secret_scan['enabled'] else 'No',
            'Secret Scanning Push Protection': 'Yes' if secret_scan.get('push_protection', False) else 'No',
            'Secret Scanning Open Alerts': secret_scan.get('open_alerts', 0),
            'Secret Scanning Status': '✅ Pass' if secret_scan['enabled'] else '❌ Fail',
            'Org Default: Secret Scanning': 'Yes' if secret_scan_default is True else 'No' if secret_scan_default is False else 'N/A',
            'Org Default: Push Protection': 'Yes' if secret_scan_pp_default is True else 'No' if secret_scan_pp_default is False else 'N/A',
            
            # Dependabot (Actual + Org Default)
            'Dependabot Enabled': 'Yes' if dependabot['enabled'] else 'No',
            'Dependabot Open Alerts': dependabot.get('open_alerts', 0),
            'Dependabot Critical Alerts': dependabot.get('critical_alerts', 0),
            'Dependabot Status': '✅ Pass' if dependabot['enabled'] else '❌ Fail',
            'Org Default: Dependabot': 'Yes' if dependabot_default is True else 'No' if dependabot_default is False else 'N/A',
            
            # Branch Protection
            'Branch Protection Enabled': 'Yes' if branch_prot['enabled'] else 'No',
            'Uses Rulesets (Recommended)': 'Yes' if branch_prot.get('uses_rulesets', False) else 'No',
            'Requires Reviews': 'Yes' if branch_prot.get('requires_reviews', False) else 'No',
            'Requires Status Checks': 'Yes' if branch_prot.get('requires_status_checks', False) else 'No',
            'Branch Protection Status': '✅ Pass' if branch_prot['enabled'] else '❌ Fail',
            
            # Overall Status
            'Overall Security Status': '✅ Pass' if all([
                code_scan['enabled'] and code_scan.get('critical_alerts', 0) == 0,
                secret_scan['enabled'],
                dependabot['enabled'],
                branch_prot['enabled']
            ]) else '❌ Fail',
            
            # Errors
            'Errors': '; '.join(filter(None, [
                code_scan.get('error'),
                secret_scan.get('error'),
                dependabot.get('error'),
                branch_prot.get('error')
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

def print_summary(results, repos, fetch_time, assess_time, total_time):
    """Print summary statistics"""
    
    # Calculate statistics
    total_repos = len(results)
    
    code_scan_enabled = sum(1 for r in results if r['code_scanning']['enabled'])
    code_scan_no_critical = sum(1 for r in results if r['code_scanning']['enabled'] and r['code_scanning'].get('critical_alerts', 0) == 0)
    
    secret_scan_enabled = sum(1 for r in results if r['secret_scanning']['enabled'])
    
    dependabot_enabled = sum(1 for r in results if r['dependabot']['enabled'])
    
    branch_prot_enabled = sum(1 for r in results if r['branch_protection']['enabled'])
    
    fully_compliant = sum(1 for r in results if all([
        r['code_scanning']['enabled'] and r['code_scanning'].get('critical_alerts', 0) == 0,
        r['secret_scanning']['enabled'],
        r['dependabot']['enabled'],
        r['branch_protection']['enabled']
    ]))
    
    log("\n" + "=" * 80)
    log("SECURITY ASSESSMENT SUMMARY")
    log("=" * 80)
    log(f"Total repositories assessed: {total_repos}")
    log(f"\n📊 SECURITY CONTROLS ADOPTION:")
    log(f"   Code Scanning enabled: {code_scan_enabled}/{total_repos} ({(code_scan_enabled/total_repos*100):.1f}%)")
    log(f"   Code Scanning with no critical alerts: {code_scan_no_critical}/{total_repos} ({(code_scan_no_critical/total_repos*100):.1f}%)")
    log(f"   Secret Scanning enabled: {secret_scan_enabled}/{total_repos} ({(secret_scan_enabled/total_repos*100):.1f}%)")
    log(f"   Dependabot enabled: {dependabot_enabled}/{total_repos} ({(dependabot_enabled/total_repos*100):.1f}%)")
    log(f"   Branch Protection enabled: {branch_prot_enabled}/{total_repos} ({(branch_prot_enabled/total_repos*100):.1f}%)")
    log(f"\n✅ FULLY COMPLIANT REPOSITORIES: {fully_compliant}/{total_repos} ({(fully_compliant/total_repos*100):.1f}%)")
    
    # Show ruleset recommendation
    using_rulesets = sum(1 for r in results if r['branch_protection'].get('uses_rulesets', False))
    using_legacy = sum(1 for r in results if r['branch_protection']['enabled'] and not r['branch_protection'].get('uses_rulesets', False))
    
    if using_legacy > 0:
        log(f"\n💡 RECOMMENDATION:")
        log(f"   {using_legacy} repositories are using legacy branch protection rules.")
        log(f"   Consider migrating to Repository Rulesets for:")
        log(f"   • Better performance and flexibility")
        log(f"   • Organization-wide rule enforcement")
        log(f"   • Bypass permissions and insights")
        log(f"   • Learn more: https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets")
    
    if using_rulesets > 0:
        log(f"\n✨ {using_rulesets} repositories are using modern Repository Rulesets!")
    
    # Show final rate limit
    if CONFIG['enable_rate_limit_check']:
        final_limit = check_rate_limit()
        if final_limit:
            log(f"\n📊 Final Rate Limit: {final_limit['remaining']}/{final_limit['limit']} requests remaining")
    
    log(f"\n⚡ PERFORMANCE METRICS:")
    log(f"   Repository fetch: {fetch_time:.2f}s")
    log(f"   Security assessment: {assess_time:.2f}s")
    log(f"   Total execution: {total_time:.2f}s")
    log(f"   Average per repo: {(assess_time/len(repos)):.3f}s")
    
    # Show non-compliant repositories
    non_compliant = [r for r in results if not all([
        r['code_scanning']['enabled'] and r['code_scanning'].get('critical_alerts', 0) == 0,
        r['secret_scanning']['enabled'],
        r['dependabot']['enabled'],
        r['branch_protection']['enabled']
    ])]
    
    if non_compliant:
        log(f"\n❌ NON-COMPLIANT REPOSITORIES ({len(non_compliant)}):")
        for result in non_compliant[:10]:  # Show first 10
            issues = []
            if not result['code_scanning']['enabled']:
                issues.append('No Code Scanning')
            elif result['code_scanning'].get('critical_alerts', 0) > 0:
                issues.append(f"{result['code_scanning']['critical_alerts']} Critical Alerts")
            if not result['secret_scanning']['enabled']:
                issues.append('No Secret Scanning')
            if not result['dependabot']['enabled']:
                issues.append('No Dependabot')
            if not result['branch_protection']['enabled']:
                issues.append('No Branch Protection')
            
            log(f"   • {result['repo_name']}: {', '.join(issues)}")
        
        if len(non_compliant) > 10:
            log(f"   ... and {len(non_compliant) - 10} more (see CSV for full list)")

def main():
    """Main execution function"""
    start_time = time()
    
    log("=" * 80)
    log("GITHUB SECURITY ASSESSMENT TOOL")
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
    
    # Fetch repositories and organization settings
    fetch_start = time()
    repos, org_settings = fetch_repositories()
    fetch_time = time() - fetch_start
    
    if not repos:
        log("\n❌ Could not fetch repositories. Make sure you're authenticated:")
        log("  gh auth login")
        return 1
    
    log(f"✓ Found {len(repos)} repositories and {len(org_settings)} organizations in {fetch_time:.2f}s")
    
    # Assess repositories
    assess_start = time()
    results = assess_all_repositories(repos, org_settings)
    assess_time = time() - assess_start
    
    # Export results
    csv_file = export_to_csv(results)
    
    # Print summary
    total_time = time() - start_time
    print_summary(results, repos, fetch_time, assess_time, total_time)
    
    log("\n" + "=" * 80)
    log("✅ Security assessment complete!")
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
