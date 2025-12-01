import subprocess
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import csv
from datetime import datetime

def run_gh_command(command):
    """Run GitHub CLI command and return JSON output"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        # Suppress error messages during parallel execution
        return None
    except json.JSONDecodeError as e:
        return None

def check_gh_installed():
    """Check if GitHub CLI is installed"""
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def check_repo_copilot(repo):
    """Check a single repository for Copilot directories"""
    full_name = repo['nameWithOwner']
    result = {
        'name': full_name,
        'has_github_dir': False,
        'folders': {
            'prompts': False,
            'instructions': False,
            'agents': False,
            'collections': False,
            'scripts': False
        },
        'error': None
    }
    
    # Check .github directory
    github_contents = run_gh_command(f'gh api repos/{full_name}/contents/.github')
    
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

def list_repos_gh():
    """List all repositories using GitHub CLI with parallel execution"""
    start_time = time.time()
    
    print("=" * 80)
    print("LISTING REPOSITORIES USING GITHUB CLI (OPTIMIZED)")
    print("=" * 80)
    
    if not check_gh_installed():
        print("\n❌ GitHub CLI (gh) is not installed!")
        print("\nTo install:")
        print("  winget install --id GitHub.cli")
        print("\nOr download from: https://cli.github.com/")
        return
    
    # Parallel fetching of repos from multiple sources
    print("Fetching repositories in parallel...")
    
    all_repos = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        
        # Fetch user repos
        futures.append(executor.submit(run_gh_command, 'gh repo list --json nameWithOwner,name,owner --limit 1000'))
        
        # Get organizations
        orgs_future = executor.submit(run_gh_command, 'gh api user/orgs --paginate')
        orgs_data = orgs_future.result()
        
        if orgs_data:
            orgs = [org['login'] for org in orgs_data]
            for org in orgs:
                futures.append(executor.submit(run_gh_command, f'gh repo list {org} --json nameWithOwner,name,owner --limit 1000'))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_repos.extend(result)
    
    # Remove duplicates based on nameWithOwner
    seen = set()
    repos = []
    for repo in all_repos:
        if repo['nameWithOwner'] not in seen:
            seen.add(repo['nameWithOwner'])
            repos.append(repo)
    
    if not repos:
        print("\n❌ Could not fetch repositories. Make sure you're authenticated:")
        print("  gh auth login")
        return
    
    fetch_time = time.time() - start_time
    print(f"✓ Found {len(repos)} repositories in {fetch_time:.2f}s\n")
    
    print("=" * 80)
    print("CHECKING COPILOT DIRECTORIES (Parallel Execution)")
    print("=" * 80)
    print()
    
    # Parallel checking of repos with progress
    check_start = time.time()
    results = []
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_repo = {executor.submit(check_repo_copilot, repo): repo for repo in repos}
        
        completed = 0
        for future in as_completed(future_to_repo):
            result = future.result()
            results.append(result)
            completed += 1
            
            # Progress indicator
            print(f"⚡ Progress: {completed}/{len(repos)} repositories checked ({(completed/len(repos)*100):.0f}%)", end='\r')
    
    print()  # New line after progress
    check_time = time.time() - check_start
    
    # Sort results by name for consistent output
    results.sort(key=lambda x: x['name'])
    
    # Display results
    print()
    repos_with_copilot = 0
    repos_checked = 0
    repos_with_errors = []
    
    for result in results:
        print(f"\n📦 {result['name']}")
        print("-" * 80)
        
        if result['error']:
            print(f"   ❌ Error: {result['error']}")
            repos_with_errors.append(result['name'])
        elif not result['has_github_dir']:
            print(f"   📁 .github directory: No")
            print(f"   prompts: No")
            print(f"   instructions: No")
            print(f"   agents: No")
            print(f"   collections: No")
            print(f"   scripts: No")
            repos_checked += 1
        else:
            print(f"   📁 .github directory: Yes")
            
            for folder, exists in result['folders'].items():
                print(f"   {folder}: {'✓ Yes' if exists else '✗ No'}")
            
            if any(result['folders'].values()):
                repos_with_copilot += 1
            
            repos_checked += 1
    
    total_time = time.time() - start_time
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total repositories: {len(repos)}")
    print(f"Repositories checked: {repos_checked}")
    print(f"Repositories with Copilot directories: {repos_with_copilot}")
    print(f"Repositories with errors: {len(repos_with_errors)}")
    print(f"\n⚡ PERFORMANCE METRICS:")
    print(f"   Repository fetch: {fetch_time:.2f}s")
    print(f"   Directory check: {check_time:.2f}s")
    print(f"   Total execution: {total_time:.2f}s")
    print(f"   Average per repo: {(check_time/len(repos)):.3f}s")
    print(f"   Speedup: ~{(len(repos) * 0.5 / check_time):.1f}x faster than sequential")
    
    if repos_with_errors:
        print(f"\n❌ Repositories with errors:")
        for repo_name in repos_with_errors:
            print(f"   - {repo_name}")
    
    # Export to CSV
    print("\n" + "=" * 80)
    print("EXPORTING TO CSV")
    print("=" * 80)
    
    export_data = []
    for result in results:
        repo_name = result['name']
        # Determine if it's personal or organization
        owner = repo_name.split('/')[0]
        
        # Check if it's an organization by looking at the original repo data
        is_org = False
        org_name = ""
        for repo in repos:
            if repo['nameWithOwner'] == repo_name:
                # If owner has 'type' field or we can check against known patterns
                is_org = owner != 'admin_tcardoso'  # Personal account
                if is_org:
                    org_name = owner
                break
        
        row = {
            'Repository': repo_name,
            'Owner': owner,
            'Type': 'Organization' if is_org else 'Personal',
            'Organization': org_name if is_org else 'N/A',
            'Has .github': 'Yes' if result['has_github_dir'] else 'No',
            'Has prompts/': 'Yes' if result['folders']['prompts'] else 'No',
            'Has instructions/': 'Yes' if result['folders']['instructions'] else 'No',
            'Has agents/': 'Yes' if result['folders']['agents'] else 'No',
            'Has collections/': 'Yes' if result['folders']['collections'] else 'No',
            'Has scripts/': 'Yes' if result['folders']['scripts'] else 'No',
            'Has Copilot Directories': 'Yes' if any(result['folders'].values()) else 'No',
            'Error': result['error'] if result['error'] else 'None'
        }
        export_data.append(row)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"github_copilot_assessment_{timestamp}.csv"
    
    # Export to CSV
    if export_data:
        fieldnames = list(export_data[0].keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(export_data)
        
        print(f"✅ CSV file created: {filename}")
        print(f"   Total rows: {len(export_data)}")
        print(f"   Columns: {len(fieldnames)}")
    else:
        print("❌ No data to export")
    
    return filename

if __name__ == "__main__":
    list_repos_gh()
