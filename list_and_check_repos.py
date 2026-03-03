import requests
import os

def list_repositories(token):
    """List all repositories accessible with the token"""
    headers = {"Authorization": f"Bearer {token}"}
    repos = []
    
    # Try to get user's repositories
    user_url = "https://api.github.com/user/repos"
    params = {"per_page": 100, "page": 1}
    
    while True:
        response = requests.get(user_url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Error listing repositories: {response.status_code}")
            print(f"Response: {response.text}")
            break
        
        page_repos = response.json()
        if not page_repos:
            break
            
        repos.extend(page_repos)
        params["page"] += 1
        
        # Check if there are more pages
        if len(page_repos) < 100:
            break
    
    return repos

def check_copilot_directories(owner, repo, token):
    """Check a specific repository for Copilot directories"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Check for .github directory
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/.github"
    response = requests.get(url, headers=headers)
    
    result = {
        "repo": f"{owner}/{repo}",
        "has_github_dir": False,
        "prompts": False,
        "instructions": False,
        "agents": False,
        "collections": False,
        "scripts": False,
        "skills": False
    }
    
    if response.status_code == 404:
        return result
    elif response.status_code != 200:
        result["error"] = f"Status {response.status_code}: {response.text}"
        return result

    result["has_github_dir"] = True
    contents = [item['name'] for item in response.json()]
    
    for folder in ["prompts", "instructions", "agents", "collections", "scripts", "skills"]:
        result[folder] = folder in contents
    
    return result

# Main execution
YOUR_GITHUB_TOKEN = "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"

print("=" * 80)
print("LISTING ALL ACCESSIBLE REPOSITORIES")
print("=" * 80)

repos = list_repositories(YOUR_GITHUB_TOKEN)
print(f"\nFound {len(repos)} repositories\n")

if not repos:
    print("No repositories found. Check token permissions.")
else:
    print("=" * 80)
    print("CHECKING COPILOT DIRECTORIES")
    print("=" * 80)
    print()
    
    for repo in repos:
        owner = repo['owner']['login']
        repo_name = repo['name']
        full_name = repo['full_name']
        
        print(f"\n📦 {full_name}")
        print("-" * 80)
        
        result = check_copilot_directories(owner, repo_name, YOUR_GITHUB_TOKEN)
        
        if "error" in result:
            print(f"   ❌ Error: {result['error']}")
        elif not result["has_github_dir"]:
            print(f"   📁 .github directory: No")
            print(f"   prompts: No")
            print(f"   instructions: No")
            print(f"   agents: No")
            print(f"   collections: No")
            print(f"   scripts: No")
            print(f"   skills: No")
        else:
            print(f"   📁 .github directory: Yes")
            print(f"   prompts: {'✓ Yes' if result['prompts'] else '✗ No'}")
            print(f"   instructions: {'✓ Yes' if result['instructions'] else '✗ No'}")
            print(f"   agents: {'✓ Yes' if result['agents'] else '✗ No'}")
            print(f"   collections: {'✓ Yes' if result['collections'] else '✗ No'}")
            print(f"   scripts: {'✓ Yes' if result['scripts'] else '✗ No'}")
            print(f"   skills: {'✓ Yes' if result['skills'] else '✗ No'}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total repositories checked: {len(repos)}")
    
    # Count repos with any Copilot directories and access errors
    repos_with_copilot = 0
    repos_with_errors = []
    repos_accessible = 0
    
    for repo in repos:
        result = check_copilot_directories(repo['owner']['login'], repo['name'], YOUR_GITHUB_TOKEN)
        
        if "error" in result:
            repos_with_errors.append({
                'name': repo['full_name'],
                'error': result['error']
            })
        else:
            repos_accessible += 1
            if result.get('prompts') or result.get('instructions') or result.get('agents') or result.get('collections') or result.get('scripts') or result.get('skills'):
                repos_with_copilot += 1
    
    print(f"Repositories with Copilot directories: {repos_with_copilot}")
    print(f"Repositories accessible: {repos_accessible}")
    print(f"Repositories with access errors: {len(repos_with_errors)}")
    
    if repos_with_errors:
        print("\n" + "=" * 80)
        print("ACCESS ERRORS DETAILS")
        print("=" * 80)
        
        # Group errors by type
        saml_errors = []
        other_errors = []
        
        for error_repo in repos_with_errors:
            if "SAML" in error_repo['error']:
                saml_errors.append(error_repo['name'])
            else:
                other_errors.append(error_repo)
        
        if saml_errors:
            print(f"\n🔒 SAML Protected Repositories ({len(saml_errors)}):")
            print("   These require token authorization with SAML SSO")
            for repo_name in saml_errors:
                print(f"   - {repo_name}")
        
        if other_errors:
            print(f"\n❌ Other Access Errors ({len(other_errors)}):")
            for error_repo in other_errors:
                print(f"   - {error_repo['name']}")
                print(f"     Error: {error_repo['error'][:100]}...")
