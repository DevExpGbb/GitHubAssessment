
import requests
import os

def check_copilot_directories(owner, repo, token):
    headers = {"Authorization": f"Bearer {token}"}
    
    # First check if the repo exists
    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    repo_response = requests.get(repo_url, headers=headers)
    
    if repo_response.status_code != 200:
        print(f"Cannot access repository {owner}/{repo}")
        print(f"Status code: {repo_response.status_code}")
        print(f"Response: {repo_response.text}")
        return
    
    print(f"✓ Repository {owner}/{repo} found")
    
    # Check for .github directory
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/.github"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 404:
        print(f"No .github directory found in {owner}/{repo}")
        print(f"copilot-agents: No")
        print(f"copilot-instructions: No")
        print(f"copilot-prompts: No")
        return
    elif response.status_code != 200:
        print(f"Error accessing .github directory")
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return

    contents = [item['name'] for item in response.json()]
    print(f"✓ .github directory found with: {', '.join(contents)}")
    for folder in ["copilot-agents", "copilot-instructions", "copilot-prompts"]:
        print(f"{folder}: {'Yes' if folder in contents else 'No'}")

# Usage
# Retrieve GitHub token from environment variable
YOUR_GITHUB_TOKEN = "ssss"
#GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
#if not GITHUB_TOKEN:
#    raise ValueError("Please set the GITHUB_TOKEN environment variable.")
check_copilot_directories("skills-introduction-to-github", "ERP-System", YOUR_GITHUB_TOKEN)
