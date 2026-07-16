#!/usr/bin/env python3
"""
GitHub Repository Hygiene Assessment Tool
Checks repositories for essential hygiene files, configurations, and staleness.

Requirements:
    - GitHub CLI (gh) installed and authenticated
    - Python 3.8+
    - Appropriate permissions to access repository contents

Usage:
    python repo_hygiene_assessment.py

Configuration:
    Edit the CONFIG section below to customize behavior

Checks performed:
    - CODEOWNERS file presence (root or .github/)
    - LICENSE file and SPDX identifier
    - SECURITY.md file presence (root or .github/)
    - README file presence
    - .gitignore file presence
    - dependabot.yml/yaml configuration
    - Private Vulnerability Reporting status
    - Stale repository detection (no push in >180 days, not archived)
"""

import subprocess
import json
import sys
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time, sleep
from datetime import datetime, timezone
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
    'csv_prefix': 'github_repo_hygiene_assessment',

    # Staleness threshold (days since last push)
    'stale_threshold_days': 180,

    # Personal account identifier (leave empty to auto-detect)
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
    except Exception:
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
    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return None


# ============================================================================
# REPOSITORY FETCHING
# ============================================================================

def fetch_repositories():
    """Fetch all accessible repositories"""
    log("Fetching repositories...")

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

        for future in as_completed(futures):
            result = future.result()
            if result and isinstance(result, list):
                all_repos.extend(result)

    # Remove duplicates
    seen = set()
    unique_repos = []
    for repo in all_repos:
        if repo['nameWithOwner'] not in seen:
            seen.add(repo['nameWithOwner'])
            unique_repos.append(repo)

    return unique_repos


# ============================================================================
# HYGIENE CHECKS
# ============================================================================

def check_codeowners(repo_name):
    """Check if CODEOWNERS file exists (root or .github/)"""
    # Check root CODEOWNERS
    result = run_gh_command(f"{CONFIG['gh_command']} api repos/{repo_name}/contents/CODEOWNERS")
    if result and isinstance(result, dict) and result.get('name'):
        return True

    # Check .github/CODEOWNERS
    result = run_gh_command(f"{CONFIG['gh_command']} api repos/{repo_name}/contents/.github/CODEOWNERS")
    if result and isinstance(result, dict) and result.get('name'):
        return True

    return False


def check_license(repo_name):
    """Check if LICENSE exists and get SPDX identifier"""
    result = run_gh_command(f"{CONFIG['gh_command']} api repos/{repo_name}/license")
    if result and isinstance(result, dict):
        license_info = result.get('license', {})
        spdx_id = license_info.get('spdx_id', 'NOASSERTION')
        return {'has_license': True, 'spdx_id': spdx_id}

    return {'has_license': False, 'spdx_id': 'None'}


def check_security_md(repo_name):
    """Check if SECURITY.md exists (root or .github/)"""
    # Check root SECURITY.md
    result = run_gh_command(f"{CONFIG['gh_command']} api repos/{repo_name}/contents/SECURITY.md")
    if result and isinstance(result, dict) and result.get('name'):
        return True

    # Check .github/SECURITY.md
    result = run_gh_command(f"{CONFIG['gh_command']} api repos/{repo_name}/contents/.github/SECURITY.md")
    if result and isinstance(result, dict) and result.get('name'):
        return True

    return False


def check_readme(repo_name):
    """Check if README exists"""
    result = run_gh_command(f"{CONFIG['gh_command']} api repos/{repo_name}/readme")
    if result and isinstance(result, dict) and result.get('name'):
        return True
    return False


def check_gitignore(repo_name):
    """Check if .gitignore exists"""
    result = run_gh_command(f"{CONFIG['gh_command']} api repos/{repo_name}/contents/.gitignore")
    if result and isinstance(result, dict) and result.get('name'):
        return True
    return False


def check_dependabot_config(repo_name):
    """Check if dependabot.yml or dependabot.yaml exists in .github/"""
    # Check .github/dependabot.yml
    result = run_gh_command(f"{CONFIG['gh_command']} api repos/{repo_name}/contents/.github/dependabot.yml")
    if result and isinstance(result, dict) and result.get('name'):
        return True

    # Check .github/dependabot.yaml
    result = run_gh_command(f"{CONFIG['gh_command']} api repos/{repo_name}/contents/.github/dependabot.yaml")
    if result and isinstance(result, dict) and result.get('name'):
        return True

    return False


def check_private_vuln_reporting(repo_name):
    """Check if Private Vulnerability Reporting is enabled"""
    result = run_gh_command(f"{CONFIG['gh_command']} api repos/{repo_name}/private-vulnerability-reporting")
    if result and isinstance(result, dict):
        return result.get('enabled', False)
    return False


def check_staleness(repo_name):
    """Check if repository is stale (no push in threshold days, not archived)"""
    result = run_gh_command(f"{CONFIG['gh_command']} api repos/{repo_name}")
    if not result or not isinstance(result, dict):
        return {'days_since_push': -1, 'is_stale': False, 'is_archived': False, 'error': 'Cannot fetch repo data'}

    pushed_at = result.get('pushed_at')
    archived = result.get('archived', False)

    if not pushed_at:
        return {'days_since_push': -1, 'is_stale': False, 'is_archived': archived, 'error': None}

    try:
        push_date = datetime.fromisoformat(pushed_at.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        days_since_push = (now - push_date).days
    except (ValueError, TypeError):
        return {'days_since_push': -1, 'is_stale': False, 'is_archived': archived, 'error': 'Cannot parse date'}

    is_stale = days_since_push > CONFIG['stale_threshold_days'] and not archived

    return {
        'days_since_push': days_since_push,
        'is_stale': is_stale,
        'is_archived': archived,
        'error': None
    }


# ============================================================================
# ASSESSMENT ORCHESTRATION
# ============================================================================

def assess_repository_hygiene(repo):
    """Perform comprehensive hygiene assessment on a repository"""
    repo_name = repo['nameWithOwner']
    owner = repo_name.split('/')[0]

    log(f"Assessing {repo_name}...", verbose_only=True)

    errors = []

    # Run all checks
    try:
        has_codeowners = check_codeowners(repo_name)
    except Exception as e:
        has_codeowners = False
        errors.append(f"CODEOWNERS: {e}")

    try:
        license_info = check_license(repo_name)
    except Exception as e:
        license_info = {'has_license': False, 'spdx_id': 'None'}
        errors.append(f"LICENSE: {e}")

    try:
        has_security_md = check_security_md(repo_name)
    except Exception as e:
        has_security_md = False
        errors.append(f"SECURITY.md: {e}")

    try:
        has_readme = check_readme(repo_name)
    except Exception as e:
        has_readme = False
        errors.append(f"README: {e}")

    try:
        has_gitignore = check_gitignore(repo_name)
    except Exception as e:
        has_gitignore = False
        errors.append(f".gitignore: {e}")

    try:
        has_dependabot = check_dependabot_config(repo_name)
    except Exception as e:
        has_dependabot = False
        errors.append(f"dependabot: {e}")

    try:
        pvr_enabled = check_private_vuln_reporting(repo_name)
    except Exception as e:
        pvr_enabled = False
        errors.append(f"PVR: {e}")

    try:
        staleness = check_staleness(repo_name)
    except Exception as e:
        staleness = {'days_since_push': -1, 'is_stale': False, 'is_archived': False, 'error': str(e)}
        errors.append(f"Staleness: {e}")

    if staleness.get('error'):
        errors.append(f"Staleness: {staleness['error']}")

    return {
        'repo_name': repo_name,
        'owner': owner,
        'is_private': repo.get('isPrivate', False),
        'has_codeowners': has_codeowners,
        'license_info': license_info,
        'has_security_md': has_security_md,
        'has_readme': has_readme,
        'has_gitignore': has_gitignore,
        'has_dependabot': has_dependabot,
        'pvr_enabled': pvr_enabled,
        'staleness': staleness,
        'errors': errors,
    }


def assess_all_repositories(repos):
    """Assess all repositories in parallel"""
    log("\nAssessing repository hygiene (parallel execution)...")

    results = []
    total = len(repos)

    with ThreadPoolExecutor(max_workers=CONFIG['max_workers_check']) as executor:
        future_to_repo = {executor.submit(assess_repository_hygiene, repo): repo for repo in repos}

        completed = 0
        for future in as_completed(future_to_repo):
            result = future.result()
            results.append(result)
            completed += 1

            log(f"⚡ Progress: {completed}/{total} repositories assessed ({(completed/total*100):.0f}%)", verbose_only=True)

    results.sort(key=lambda x: x['repo_name'])
    return results


# ============================================================================
# CSV EXPORT
# ============================================================================

def export_to_csv(results):
    """Export results to CSV"""
    log("\n" + "=" * 80)
    log("EXPORTING TO CSV")
    log("=" * 80)

    export_data = []

    for result in results:
        repo_name = result['repo_name']
        owner = result['owner']
        is_private = result['is_private']
        staleness = result['staleness']

        has_codeowners = result['has_codeowners']
        has_license = result['license_info']['has_license']
        license_type = result['license_info']['spdx_id']
        has_security_md = result['has_security_md']
        has_readme = result['has_readme']
        has_gitignore = result['has_gitignore']
        has_dependabot = result['has_dependabot']
        pvr_enabled = result['pvr_enabled']
        days_since_push = staleness['days_since_push']
        is_stale = staleness['is_stale']
        is_archived = staleness['is_archived']

        # Generate recommendations
        recommendations = []
        if not has_codeowners:
            recommendations.append('Add CODEOWNERS')
        if not has_license:
            recommendations.append('Add LICENSE')
        if not has_security_md:
            recommendations.append('Add SECURITY.md')
        if not has_readme:
            recommendations.append('Add README')
        if not has_gitignore:
            recommendations.append('Add .gitignore')
        if not has_dependabot:
            recommendations.append('Add dependabot.yml')
        if not pvr_enabled:
            recommendations.append('Enable Private Vulnerability Reporting')
        if is_stale:
            recommendations.append('Archive or update stale repository')

        # Overall status: Pass if has CODEOWNERS + LICENSE + SECURITY.md + README + not stale (or archived)
        is_passing = all([
            has_codeowners,
            has_license,
            has_security_md,
            has_readme,
            not is_stale or is_archived,
        ])

        overall_status = '✅ Pass' if is_passing else '❌ Fail'

        row = {
            'Repository': repo_name,
            'Owner': owner,
            'Visibility': 'Private' if is_private else 'Public',
            'Has CODEOWNERS': 'Yes' if has_codeowners else 'No',
            'Has LICENSE': 'Yes' if has_license else 'No',
            'License Type': license_type,
            'Has SECURITY.md': 'Yes' if has_security_md else 'No',
            'Has README': 'Yes' if has_readme else 'No',
            'Has .gitignore': 'Yes' if has_gitignore else 'No',
            'Has dependabot.yml': 'Yes' if has_dependabot else 'No',
            'Private Vuln Reporting': 'Yes' if pvr_enabled else 'No',
            'Days Since Last Push': days_since_push if days_since_push >= 0 else 'Unknown',
            'Is Stale': 'Yes' if is_stale else 'No',
            'Is Archived': 'Yes' if is_archived else 'No',
            'Overall Hygiene Status': overall_status,
            'Recommendations': '; '.join(recommendations) if recommendations else 'None',
            'Errors': '; '.join(result['errors']) if result['errors'] else 'None',
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


# ============================================================================
# SUMMARY
# ============================================================================

def print_summary(results, repos, fetch_time, assess_time, total_time):
    """Print summary statistics"""
    total_repos = len(results)

    has_codeowners_count = sum(1 for r in results if r['has_codeowners'])
    has_license_count = sum(1 for r in results if r['license_info']['has_license'])
    has_security_count = sum(1 for r in results if r['has_security_md'])
    has_readme_count = sum(1 for r in results if r['has_readme'])
    has_gitignore_count = sum(1 for r in results if r['has_gitignore'])
    has_dependabot_count = sum(1 for r in results if r['has_dependabot'])
    pvr_enabled_count = sum(1 for r in results if r['pvr_enabled'])
    stale_count = sum(1 for r in results if r['staleness']['is_stale'])
    archived_count = sum(1 for r in results if r['staleness']['is_archived'])

    fully_compliant = sum(1 for r in results if all([
        r['has_codeowners'],
        r['license_info']['has_license'],
        r['has_security_md'],
        r['has_readme'],
        not r['staleness']['is_stale'] or r['staleness']['is_archived'],
    ]))

    log("\n" + "=" * 80)
    log("REPOSITORY HYGIENE ASSESSMENT SUMMARY")
    log("=" * 80)
    log(f"Total repositories assessed: {total_repos}")

    log(f"\n📊 HYGIENE CONTROLS ADOPTION:")
    log(f"   CODEOWNERS present:              {has_codeowners_count}/{total_repos} ({(has_codeowners_count/total_repos*100):.1f}%)")
    log(f"   LICENSE present:                 {has_license_count}/{total_repos} ({(has_license_count/total_repos*100):.1f}%)")
    log(f"   SECURITY.md present:             {has_security_count}/{total_repos} ({(has_security_count/total_repos*100):.1f}%)")
    log(f"   README present:                  {has_readme_count}/{total_repos} ({(has_readme_count/total_repos*100):.1f}%)")
    log(f"   .gitignore present:              {has_gitignore_count}/{total_repos} ({(has_gitignore_count/total_repos*100):.1f}%)")
    log(f"   dependabot.yml present:          {has_dependabot_count}/{total_repos} ({(has_dependabot_count/total_repos*100):.1f}%)")
    log(f"   Private Vuln Reporting enabled:  {pvr_enabled_count}/{total_repos} ({(pvr_enabled_count/total_repos*100):.1f}%)")

    log(f"\n📅 REPOSITORY FRESHNESS:")
    log(f"   Active repositories:  {total_repos - stale_count - archived_count}")
    log(f"   Stale repositories:   {stale_count} (no push in >{CONFIG['stale_threshold_days']} days)")
    log(f"   Archived repositories: {archived_count}")

    log(f"\n✅ FULLY COMPLIANT REPOSITORIES: {fully_compliant}/{total_repos} ({(fully_compliant/total_repos*100):.1f}%)")

    # Show final rate limit
    if CONFIG['enable_rate_limit_check']:
        final_limit = check_rate_limit()
        if final_limit:
            log(f"\n📊 Final Rate Limit: {final_limit['remaining']}/{final_limit['limit']} requests remaining")

    log(f"\n⚡ PERFORMANCE METRICS:")
    log(f"   Repository fetch: {fetch_time:.2f}s")
    log(f"   Hygiene assessment: {assess_time:.2f}s")
    log(f"   Total execution: {total_time:.2f}s")
    log(f"   Average per repo: {(assess_time/len(repos)):.3f}s")

    # Show non-compliant repositories
    non_compliant = [r for r in results if not all([
        r['has_codeowners'],
        r['license_info']['has_license'],
        r['has_security_md'],
        r['has_readme'],
        not r['staleness']['is_stale'] or r['staleness']['is_archived'],
    ])]

    if non_compliant:
        log(f"\n❌ NON-COMPLIANT REPOSITORIES ({len(non_compliant)}):")
        for result in non_compliant[:10]:
            issues = []
            if not result['has_codeowners']:
                issues.append('No CODEOWNERS')
            if not result['license_info']['has_license']:
                issues.append('No LICENSE')
            if not result['has_security_md']:
                issues.append('No SECURITY.md')
            if not result['has_readme']:
                issues.append('No README')
            if result['staleness']['is_stale']:
                issues.append(f"Stale ({result['staleness']['days_since_push']} days)")

            log(f"   • {result['repo_name']}: {', '.join(issues)}")

        if len(non_compliant) > 10:
            log(f"   ... and {len(non_compliant) - 10} more (see CSV for full list)")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main execution function"""
    start_time = time()

    log("=" * 80)
    log("GITHUB REPOSITORY HYGIENE ASSESSMENT TOOL")
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

    # Fetch repositories
    fetch_start = time()
    repos = fetch_repositories()
    fetch_time = time() - fetch_start

    if not repos:
        log("\n❌ Could not fetch repositories. Make sure you're authenticated:")
        log("  gh auth login")
        return 1

    log(f"✓ Found {len(repos)} repositories in {fetch_time:.2f}s")

    # Assess repositories
    assess_start = time()
    results = assess_all_repositories(repos)
    assess_time = time() - assess_start

    # Export results
    csv_file = export_to_csv(results)

    # Print summary
    total_time = time() - start_time
    print_summary(results, repos, fetch_time, assess_time, total_time)

    log("\n" + "=" * 80)
    log("✅ Repository hygiene assessment complete!")
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
