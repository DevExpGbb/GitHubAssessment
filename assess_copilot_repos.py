#!/usr/bin/env python3
"""
GitHub Copilot Directory Assessment Tool
Scans GitHub repositories for Copilot workspace directories and exports results to CSV.

Requirements:
    - GitHub CLI (gh) installed and authenticated
    - Python 3.7+

Usage:
    python assess_copilot_repos.py
    
Configuration:
    Edit the CONFIG section below to customize behavior
"""

import subprocess
import json
import sys
import csv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time, sleep
from datetime import datetime
from pathlib import Path
import threading

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # GitHub CLI command (change if gh is not in PATH)
    'gh_command': 'gh',
    
    # Directories to check in .github folder
    'copilot_dirs': ['prompts', 'instructions', 'agents', 'collections', 'scripts'],
    
    # Performance settings
    'max_workers_fetch': 10,     # Parallel workers for fetching repos
    'max_workers_check': 15,      # Parallel workers for checking directories
    
    # Rate limiting (for large enterprise scenarios with 1000s of repos)
    'enable_rate_limit_check': True,   # Check GitHub rate limits
    'rate_limit_threshold': 100,        # Pause if remaining requests < this
    'rate_limit_wait_time': 60,         # Seconds to wait when rate limited
    'request_delay': 0.05,              # Delay between requests (seconds)
    
    # Output settings
    'output_dir': '.',            # Where to save CSV files (. = current directory)
    'csv_prefix': 'github_copilot_assessment',
    'include_timestamp': True,
    
    # Personal account identifier (used to detect personal vs org repos)
    'personal_account': 'admin_tcardoso',
    
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
    """Check if GitHub CLI is installed and accessible"""
    try:
        result = subprocess.run(
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
        # Check rate limit periodically
        if not rate_limit_info['checked'] or rate_limit_info['remaining'] is None:
            limit_data = check_rate_limit()
            if limit_data:
                rate_limit_info['remaining'] = limit_data['remaining']
                rate_limit_info['reset_time'] = limit_data['reset_time']
                rate_limit_info['checked'] = True
                
                log(f"📊 Rate Limit: {limit_data['remaining']}/{limit_data['limit']} requests remaining", verbose_only=True)
                
                # If approaching threshold, wait
                if limit_data['remaining'] < CONFIG['rate_limit_threshold']:
                    wait_time = CONFIG['rate_limit_wait_time']
                    log(f"⚠️  Rate limit threshold reached ({limit_data['remaining']} remaining)")
                    log(f"   Waiting {wait_time} seconds before continuing...")
                    sleep(wait_time)
                    rate_limit_info['checked'] = False  # Recheck after waiting
        
        # Small delay between requests
        if CONFIG['request_delay'] > 0:
            sleep(CONFIG['request_delay'])

def run_gh_command(command):
    """Run GitHub CLI command and return JSON output"""
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
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return None

def fetch_repositories():
    """Fetch all accessible repositories in parallel"""
    log("Fetching repositories in parallel...")
    
    # Check initial rate limit
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
            f"{CONFIG['gh_command']} repo list --json nameWithOwner,name,owner --limit 1000"
        ))
        
        # Get and fetch organization repos
        orgs_future = executor.submit(
            run_gh_command,
            f"{CONFIG['gh_command']} api user/orgs --paginate"
        )
        orgs_data = orgs_future.result()
        
        if orgs_data:
            for org in orgs_data:
                futures.append(executor.submit(
                    run_gh_command,
                    f"{CONFIG['gh_command']} repo list {org['login']} --json nameWithOwner,name,owner --limit 1000"
                ))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_repos.extend(result)
    
    # Remove duplicates
    seen = set()
    unique_repos = []
    for repo in all_repos:
        if repo['nameWithOwner'] not in seen:
            seen.add(repo['nameWithOwner'])
            unique_repos.append(repo)
    
    return unique_repos

def check_repo_copilot(repo):
    """Check a single repository for Copilot directories"""
    full_name = repo['nameWithOwner']
    result = {
        'name': full_name,
        'has_github_dir': False,
        'folders': {folder: False for folder in CONFIG['copilot_dirs']},
        'error': None
    }
    
    github_contents = run_gh_command(
        f"{CONFIG['gh_command']} api repos/{full_name}/contents/.github"
    )
    
    if github_contents is None:
        return result
    elif isinstance(github_contents, dict) and 'message' in github_contents:
        result['error'] = github_contents.get('message', 'Unknown error')
        return result
    else:
        result['has_github_dir'] = True
        folder_names = [item['name'] for item in github_contents if item['type'] == 'dir']
        
        for folder in result['folders'].keys():
            result['folders'][folder] = folder in folder_names
    
    return result

def check_all_repositories(repos):
    """Check all repositories for Copilot directories in parallel"""
    log("\nChecking Copilot directories (parallel execution)...")
    
    results = []
    total = len(repos)
    
    with ThreadPoolExecutor(max_workers=CONFIG['max_workers_check']) as executor:
        future_to_repo = {executor.submit(check_repo_copilot, repo): repo for repo in repos}
        
        completed = 0
        for future in as_completed(future_to_repo):
            result = future.result()
            results.append(result)
            completed += 1
            
            # Progress indicator
            log(f"⚡ Progress: {completed}/{total} repositories checked ({(completed/total*100):.0f}%)", verbose_only=True)
    
    # Sort by name for consistent output
    results.sort(key=lambda x: x['name'])
    return results

def export_to_csv(results, repos):
    """Export results to CSV file"""
    log("\n" + "=" * 80)
    log("EXPORTING TO CSV")
    log("=" * 80)
    
    export_data = []
    
    for result in results:
        repo_name = result['name']
        owner = repo_name.split('/')[0]
        is_org = owner != CONFIG['personal_account']
        
        row = {
            'Repository': repo_name,
            'Owner': owner,
            'Type': 'Organization' if is_org else 'Personal',
            'Organization': owner if is_org else 'N/A',
            'Has .github': 'Yes' if result['has_github_dir'] else 'No',
        }
        
        # Add columns for each copilot directory
        for folder in CONFIG['copilot_dirs']:
            row[f'Has {folder}/'] = 'Yes' if result['folders'][folder] else 'No'
        
        row['Has Copilot Directories'] = 'Yes' if any(result['folders'].values()) else 'No'
        row['Error'] = result['error'] if result['error'] else 'None'
        
        export_data.append(row)
    
    # Generate filename - always include date and time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{CONFIG['csv_prefix']}_{timestamp}.csv"
    filepath = Path(CONFIG['output_dir']) / filename
    
    # Ensure output directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # Write CSV
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

def print_summary(results, repos, fetch_time, check_time, total_time):
    """Print summary statistics"""
    repos_checked = sum(1 for r in results if not r['error'])
    repos_with_copilot = sum(1 for r in results if any(r['folders'].values()))
    repos_with_errors = sum(1 for r in results if r['error'])
    
    log("\n" + "=" * 80)
    log("SUMMARY")
    log("=" * 80)
    log(f"Total repositories: {len(repos)}")
    log(f"Repositories checked: {repos_checked}")
    log(f"Repositories with Copilot directories: {repos_with_copilot}")
    log(f"Repositories with errors: {repos_with_errors}")
    
    # Show final rate limit status for enterprise monitoring
    if CONFIG['enable_rate_limit_check']:
        final_limit = check_rate_limit()
        if final_limit:
            log(f"\n📊 Final Rate Limit: {final_limit['remaining']}/{final_limit['limit']} requests remaining")
    
    log(f"\n⚡ PERFORMANCE METRICS:")
    log(f"   Repository fetch: {fetch_time:.2f}s")
    log(f"   Directory check: {check_time:.2f}s")
    log(f"   Total execution: {total_time:.2f}s")
    log(f"   Average per repo: {(check_time/len(repos)):.3f}s")
    log(f"   Speedup: ~{(len(repos) * 0.5 / check_time):.1f}x faster than sequential")
    
    # Show repositories with Copilot directories
    if repos_with_copilot > 0:
        log(f"\n✅ REPOSITORIES WITH COPILOT DIRECTORIES:")
        for result in results:
            if any(result['folders'].values()):
                found_dirs = [f for f, exists in result['folders'].items() if exists]
                log(f"   • {result['name']}: {', '.join(found_dirs)}")

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main execution function"""
    start_time = time()
    
    log("=" * 80)
    log("GITHUB COPILOT DIRECTORY ASSESSMENT TOOL")
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
    
    # Check repositories
    check_start = time()
    results = check_all_repositories(repos)
    check_time = time() - check_start
    
    # Export results
    csv_file = export_to_csv(results, repos)
    
    # Print summary
    total_time = time() - start_time
    print_summary(results, repos, fetch_time, check_time, total_time)
    
    log("\n" + "=" * 80)
    log("✅ Assessment complete!")
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
        sys.exit(1)
