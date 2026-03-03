import subprocess
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

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
        print(f"Error running command: {command}")
        print(f"Error: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from command: {command}")
        return None

def check_gh_installed():
    """Check if GitHub CLI is installed"""
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def list_repos_gh():
    """List all repositories using GitHub CLI"""
    print("=" * 80)
    print("LISTING REPOSITORIES USING GITHUB CLI")
    print("=" * 80)
    
    if not check_gh_installed():
        print("\n❌ GitHub CLI (gh) is not installed!")
        print("\nTo install:")
        print("  winget install --id GitHub.cli")
        print("\nOr download from: https://cli.github.com/")
        return
    
    # Get repos for authenticated user
    user_repos = run_gh_command('gh repo list --json nameWithOwner,name,owner --limit 1000')
    
    # List organizations the user has access to
    orgs_data = run_gh_command('gh api user/orgs --paginate')
    orgs = [org['login'] for org in orgs_data] if orgs_data else []
    org_repos = []
    for org in orgs:
        print(f"Fetching repos from {org}...")
        repos_from_org = run_gh_command(f'gh repo list {org} --json nameWithOwner,name,owner --limit 1000')
        if repos_from_org:
            org_repos.extend(repos_from_org)
    
    # Combine all repos and remove duplicates
    all_repos = user_repos if user_repos else []
    if org_repos:
        all_repos.extend(org_repos)
    
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
    
    print(f"\nFound {len(repos)} repositories\n")
    
    print("=" * 80)
    print("CHECKING COPILOT DIRECTORIES")
    print("=" * 80)
    print()
    
    repos_with_copilot = 0
    repos_checked = 0
    repos_with_errors = []
    
    for repo in repos:
        full_name = repo['nameWithOwner']
        print(f"\n📦 {full_name}")
        print("-" * 80)
        
        # Check .github directory
        github_contents = run_gh_command(f'gh api repos/{full_name}/contents/.github')
        
        if github_contents is None:
            print(f"   📁 .github directory: No")
            print(f"   prompts: No")
            print(f"   instructions: No")
            print(f"   agents: No")
            print(f"   collections: No")
            print(f"   scripts: No")
            print(f"   skills: No")
            repos_checked += 1
        elif isinstance(github_contents, dict) and 'message' in github_contents:
            print(f"   ❌ Error: {github_contents.get('message', 'Unknown error')}")
            repos_with_errors.append(full_name)
        else:
            print(f"   📁 .github directory: Yes")
            
            folder_names = [item['name'] for item in github_contents if item['type'] == 'dir']
            
            folders = {
                'prompts': 'prompts' in folder_names,
                'instructions': 'instructions' in folder_names,
                'agents': 'agents' in folder_names,
                'collections': 'collections' in folder_names,
                'scripts': 'scripts' in folder_names,
                'skills': 'skills' in folder_names
            }
            
            for folder, exists in folders.items():
                print(f"   {folder}: {'✓ Yes' if exists else '✗ No'}")
            
            if any(folders.values()):
                repos_with_copilot += 1
            
            repos_checked += 1
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total repositories: {len(repos)}")
    print(f"Repositories checked: {repos_checked}")
    print(f"Repositories with Copilot directories: {repos_with_copilot}")
    print(f"Repositories with errors: {len(repos_with_errors)}")
    
    if repos_with_errors:
        print(f"\n❌ Repositories with errors:")
        for repo_name in repos_with_errors:
            print(f"   - {repo_name}")

if __name__ == "__main__":
    list_repos_gh()
