# AGENTS.md - GitHub Assessment Tool Documentation for LLM Coding Agents

## Repository Overview

This is a **GitHub Enterprise Repository Best Practices Assessment Tool** written in Python. It provides automated assessment of GitHub repositories to ensure they meet enterprise security requirements, compliance standards, and follow best practices for AI-assisted development with GitHub Copilot.

**Repository**: DevExpGbb/GitHubAssessment  
**Language**: Python 3.7+  
**Dependencies**: GitHub CLI (gh), subprocess, json, csv, concurrent.futures  
**License**: [Not specified]

## Purpose

The tool performs three main types of assessments:
1. **Security Assessment** - Evaluates repository-level security controls
2. **Identity & Access Management (IDP) Assessment** - Validates organization-level SSO, MFA, permissions, and token security
3. **GitHub Copilot Best Practices Assessment** - Validates proper Copilot workspace directory structure

## Project Structure

```
GitHubAssessment/
├── security_assessment.py           # Main: Repository security controls assessment
├── idp_assessment.py                # Main: Identity & access management assessment  
├── assess_copilot_repos.py          # Main: GitHub Copilot best practices validation
├── list_repos_gh_cli.py            # Utility: Basic repository listing
├── list_repos_gh_cli_optimized.py  # Utility: Optimized repository listing with Copilot checks
├── list_and_check_repos.py         # Utility: Combined listing and Copilot directory checking
├── .gitignore                      # Excludes .venv, __pycache__, *.csv, *.log
├── README.md                       # Human-readable documentation
└── AGENTS.md                       # This file - LLM agent documentation
```

### Generated Files (Excluded from Git)
- `github_security_assessment_YYYYMMDD_HHMMSS.csv` - Security assessment reports
- `github_idp_assessment_YYYYMMDD_HHMMSS.csv` - IDP assessment reports
- `github_copilot_assessment_YYYYMMDD_HHMMSS.csv` - Copilot assessment reports
- `.venv/` - Python virtual environment directory

## Codebase Architecture

### Design Patterns

**Parallel Execution Pattern**: All three main assessment scripts use Python's `concurrent.futures.ThreadPoolExecutor` for parallel processing:
- Repository fetching: 10 parallel workers (configurable via `max_workers_fetch`)
- Assessment checking: 10-15 parallel workers (configurable via `max_workers_check`)
- Thread-safe rate limiting with `threading.Lock()`

**Configuration Pattern**: Each script has a `CONFIG` dictionary at the top for easy customization:
```python
CONFIG = {
    'gh_command': 'gh',
    'max_workers': 10,
    'enable_rate_limit_check': True,
    'rate_limit_threshold': 100,
    'request_delay': 0.05,
    'output_dir': '.',
    'verbose': True,
}
```

**External Command Execution**: All scripts rely on GitHub CLI (`gh`) for API access via `subprocess.run()`:
- Avoids direct GitHub API token management
- Leverages existing `gh` authentication
- Uses JSON output format for parsing

### Core Components

#### 1. security_assessment.py (695 lines)

**Purpose**: Assesses repository-level security controls across all accessible repositories.

**Key Functions**:
- `check_gh_installed()` - Validates GitHub CLI availability
- `check_rate_limit()` - Monitors GitHub API rate limits
- `get_authenticated_user()` - Gets current authenticated user info
- `fetch_all_repos()` - Fetches all accessible repositories with parallel execution
- `assess_code_scanning(repo)` - Checks Code Scanning status and critical alerts
- `assess_secret_scanning(repo)` - Validates Secret Scanning and push protection
- `assess_dependabot(repo)` - Verifies Dependabot alerts and configuration
- `assess_branch_protection(repo)` - Checks branch protection rules and rulesets
- `assess_repo_security(repo)` - Main assessment orchestrator for a single repository
- `generate_csv_report(results, filename)` - Exports results to timestamped CSV
- `main()` - Entry point with parallel assessment execution

**Security Checks**:
- Code Scanning: Enabled status, critical alerts count
- Secret Scanning: Enabled status, push protection, open alerts
- Dependabot: Enabled status, open alerts, critical alerts
- Branch Protection: Enabled status (rulesets vs legacy), review requirements
- Organization defaults for new repositories

**Output CSV Columns**:
```
Repository, Owner, Type, Visibility, Code Scanning Enabled, Code Scanning Critical Alerts,
Secret Scanning Enabled, Secret Scanning Push Protection, Secret Scanning Open Alerts,
Dependabot Enabled, Dependabot Open Alerts, Dependabot Critical Alerts,
Branch Protection Enabled, Branch Protection Type, Overall Security Status, Errors
```

#### 2. idp_assessment.py (609 lines)

**Purpose**: Evaluates organization-level identity, authentication, and access controls.

**Key Functions**:
- `get_authenticated_user()` - Gets current user's organization memberships
- `fetch_all_orgs()` - Fetches all accessible organizations
- `assess_sso_auth(org)` - Checks SSO/OIDC configuration (Enterprise-level)
- `assess_2fa_requirement(org)` - Verifies 2FA enforcement
- `assess_granular_permissions(org)` - Audits default repository permissions
- `assess_environment_segregation(org)` - Validates deployment environments
- `assess_token_security(org)` - Reviews Advanced Security settings for new repos
- `assess_org_idp(org)` - Main assessment orchestrator for an organization
- `generate_csv_report(results, filename)` - Exports results to CSV
- `main()` - Entry point with parallel organization assessment

**IDP Checks**:
- SSO/Authentication: Enterprise SSO status, 2FA requirement, IP allowlist
- Permissions: Default member repository permissions, member capabilities
- Environment Segregation: Deployment environments usage
- Token Security: Advanced Security, Secret Scanning, Dependabot for new repos

**Output CSV Columns**:
```
Organization, Plan, Enterprise Status, 2FA Required, Enterprise SSO,
IP Allowlist Enabled, Default Repo Permission, Members Can Create Repos,
Members Can Fork Private Repos, Environments Count, Environment Names,
Advanced Security New Repos, Secret Scanning New Repos, Dependabot New Repos,
Overall IAM Status, Verification Notes, Errors
```

**Important Note**: For Enterprise organizations using Entra ID (Azure AD), the tool cannot query IdP settings directly through GitHub API. It provides manual verification instructions for checking Azure Portal.

#### 3. assess_copilot_repos.py (412 lines)

**Purpose**: Validates GitHub Copilot workspace directory structure across all repositories.

**Key Functions**:
- `check_gh_installed()` - Validates GitHub CLI
- `check_rate_limit()` - Monitors API rate limits
- `get_authenticated_user()` - Gets current user info
- `fetch_all_repos()` - Fetches all repositories with parallel execution
- `check_copilot_dirs(repo)` - Checks for Copilot workspace directories in `.github/`
- `assess_repo(repo)` - Main assessment for a single repository
- `generate_csv_report(results, filename)` - Exports results to CSV
- `main()` - Entry point with parallel assessment

**Copilot Directory Structure Validation**:
```
.github/
├── prompts/            # Task-specific prompts (.prompt.md files)
├── instructions/       # Coding standards (.instructions.md files)
├── agents/            # AI personas (.agent.md files)
├── collections/       # Curated collections (.collection.yml files)
└── scripts/           # Utility scripts for maintenance
```

**Output CSV Columns**:
```
Repository, Owner, Visibility, Has .github Dir, Prompts Dir, Prompts Count,
Instructions Dir, Instructions Count, Agents Dir, Agents Count, Collections Dir,
Collections Count, Scripts Dir, Scripts Count, Overall Copilot Status, Recommendations, Errors
```

#### 4. Utility Scripts

**list_repos_gh_cli.py** (143 lines):
- Basic repository listing using GitHub CLI
- Lists user repos and organization repos separately
- Simple, non-parallelized approach
- Good for debugging and understanding repository access

**list_repos_gh_cli_optimized.py** (262 lines):
- Optimized repository listing with Copilot directory checking
- Uses parallel execution with ThreadPoolExecutor
- Exports results to CSV with timestamp
- More efficient for large-scale checking

**list_and_check_repos.py** (163 lines):
- Uses GitHub API directly (requires token)
- Combined listing and Copilot directory checking
- Alternative to GitHub CLI approach
- Useful when direct API access is preferred

## Development Guidelines

### Prerequisites
- Python 3.7 or higher
- GitHub CLI (gh) installed and authenticated
- Appropriate GitHub permissions:
  - Repository read access for security/Copilot assessments
  - Organization admin/owner for IDP assessment

### Setting Up Development Environment

```bash
# Clone repository
git clone <repository-url>
cd GitHubAssessment

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/Mac:
source .venv/bin/activate

# Install GitHub CLI (if not installed)
# Windows:
winget install --id GitHub.cli
# macOS:
brew install gh
# Linux: See https://cli.github.com/

# Authenticate with GitHub CLI
gh auth login
```

### Code Style and Conventions

1. **Shebang**: All main scripts use `#!/usr/bin/env python3`
2. **Docstrings**: Module-level docstrings explain purpose, requirements, and usage
3. **Configuration**: Centralized CONFIG dictionary at the top of each script
4. **Error Handling**: Try-except blocks with graceful degradation
5. **Logging**: `log(message, verbose_only=False)` function for conditional output
6. **Rate Limiting**: Thread-safe rate limit checking with configurable thresholds
7. **CSV Output**: Timestamped filenames with `YYYYMMDD_HHMMSS` format
8. **Unicode Symbols**: ✅ ❌ ⚠️ 🔍 for status indicators

### Common Patterns

**Running GitHub CLI Commands**:
```python
def run_gh_command(command):
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        check=True,
        timeout=10
    )
    return json.loads(result.stdout)
```

**Parallel Execution**:
```python
with ThreadPoolExecutor(max_workers=CONFIG['max_workers']) as executor:
    futures = {executor.submit(assess_function, item): item for item in items}
    for future in as_completed(futures):
        result = future.result()
        results.append(result)
```

**Rate Limit Checking**:
```python
with rate_limit_lock:
    if rate_limit_info['remaining'] < CONFIG['rate_limit_threshold']:
        log(f"⚠️ Rate limit low, waiting {wait_time} seconds...")
        sleep(wait_time)
```

### Modifying Assessment Logic

To add a new security check to `security_assessment.py`:

1. Create a new assessment function:
```python
def assess_new_check(repo):
    """Assess new security check for repository"""
    repo_name = repo['nameWithOwner']
    try:
        # Run gh command to check the feature
        result = run_gh_command(f"gh api repos/{repo_name}/new-endpoint")
        
        return {
            'enabled': result.get('enabled', False),
            'status': '✅ Pass' if result.get('enabled') else '❌ Fail'
        }
    except Exception as e:
        return {'enabled': False, 'status': '❌ Fail', 'error': str(e)}
```

2. Add it to `assess_repo_security()`:
```python
def assess_repo_security(repo):
    # ... existing assessments ...
    new_check = assess_new_check(repo)
    
    return {
        # ... existing fields ...
        'new_check_enabled': new_check['enabled'],
        'new_check_status': new_check['status'],
    }
```

3. Update CSV headers and row generation in `generate_csv_report()`

### Testing and Validation

**Manual Testing**:
```bash
# Test with verbose output
python security_assessment.py

# Check CSV output
ls -ltr *.csv | tail -1

# Verify CSV content
head -20 github_security_assessment_*.csv
```

**Testing Rate Limiting**:
```python
# Temporarily lower threshold in CONFIG
CONFIG = {
    'rate_limit_threshold': 4000,  # Lower to trigger more rate limit checks
    'verbose': True,  # Enable verbose output to see rate limit messages
}
```

**Testing with Limited Repositories**:
Modify `fetch_all_repos()` to limit results:
```python
# In fetch_all_repos function, add:
all_repos = all_repos[:10]  # Test with first 10 repos only
```

### Common Issues and Solutions

**Issue**: "GitHub CLI (gh) is not installed"
- **Solution**: Install GitHub CLI using package manager (winget, brew, apt)

**Issue**: "Error: HTTP 401: Bad credentials"
- **Solution**: Re-authenticate with `gh auth login`

**Issue**: "Rate limit exceeded"
- **Solution**: Increase `request_delay` or decrease `max_workers` in CONFIG

**Issue**: "Permission denied when accessing organization settings"
- **Solution**: Requires organization admin/owner role for IDP assessment

**Issue**: CSV files committed to repository
- **Solution**: Check `.gitignore` includes `*.csv`

### Performance Optimization

For large organizations (100+ repositories):

1. **Adjust parallel workers**:
```python
CONFIG = {
    'max_workers_fetch': 15,  # Increase for faster fetching
    'max_workers_check': 20,  # Increase for faster checking
}
```

2. **Disable rate limit checking** (not recommended for very large orgs):
```python
CONFIG = {
    'enable_rate_limit_check': False,  # Skip rate limit checks
}
```

3. **Increase request delay** (if hitting rate limits):
```python
CONFIG = {
    'request_delay': 0.1,  # Double the delay between requests
}
```

### GitHub API Endpoints Used

The scripts use GitHub CLI which calls these API endpoints internally:

**Repository Listing**:
- `GET /user/repos` - User's repositories
- `GET /orgs/{org}/repos` - Organization repositories

**Security Assessment**:
- `GET /repos/{owner}/{repo}/code-scanning/alerts` - Code scanning alerts
- `GET /repos/{owner}/{repo}/secret-scanning/alerts` - Secret scanning alerts
- `GET /repos/{owner}/{repo}/dependabot/alerts` - Dependabot alerts
- `GET /repos/{owner}/{repo}/branches/{branch}/protection` - Branch protection
- `GET /repos/{owner}/{repo}/rulesets` - Repository rulesets

**IDP Assessment**:
- `GET /orgs/{org}` - Organization details
- `GET /orgs/{org}/repos?type=all&per_page=1` - Repository count check

**Copilot Assessment**:
- `GET /repos/{owner}/{repo}/contents/.github` - .github directory contents
- `GET /repos/{owner}/{repo}/contents/.github/{dir}` - Specific directory contents

### Adding New Assessment Types

To create a new assessment script:

1. Copy an existing assessment script (e.g., `security_assessment.py`)
2. Update the module docstring and CONFIG
3. Implement new assessment functions
4. Update `assess_main_function()` to call new checks
5. Update `generate_csv_report()` with new columns
6. Update README.md with usage instructions
7. Add to `.gitignore` if generating new file types

### CSV Output Schema

All CSV files follow this structure:
- **Timestamped filenames**: `{prefix}_YYYYMMDD_HHMMSS.csv`
- **UTF-8 encoding** with BOM (Excel-compatible)
- **Header row**: Column names describing each field
- **Status symbols**: ✅ (Pass), ❌ (Fail), ⚠️ (Review), 🔍 (Check manually)

## Deployment and Usage

### Running Assessments

**Basic Usage**:
```bash
# Security assessment
python security_assessment.py

# IDP assessment  
python idp_assessment.py

# Copilot assessment
python assess_copilot_repos.py
```

**Recommended Workflow**:
```bash
# 1. Activate virtual environment
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows

# 2. Check GitHub CLI authentication
gh auth status

# 3. Run assessments in recommended order
python assess_copilot_repos.py      # Fast - checks directory structure
python security_assessment.py       # Medium - checks security controls
python idp_assessment.py            # Slow - checks organization settings

# 4. Review CSV outputs
ls -ltr *.csv | tail -3
```

### Interpreting Results

**Console Output**:
- Progress indicators with repository count
- Real-time statistics and rate limit status
- Summary with adoption percentages
- Top non-compliant items (first 10)
- Performance metrics (execution time)

**CSV Output**:
- One row per repository (security/Copilot) or organization (IDP)
- Status columns with ✅ Pass / ❌ Fail indicators
- Quantitative metrics (alert counts, directory counts)
- Error column for troubleshooting
- Overall status column for quick filtering

### Filtering and Analysis

**PowerShell Examples**:
```powershell
# Find repositories failing security checks
Import-Csv github_security_assessment_*.csv | 
    Where-Object {$_.'Overall Security Status' -eq '❌ Fail'} |
    Select-Object Repository, 'Code Scanning Enabled', 'Secret Scanning Enabled'

# Count repositories with Copilot setup
Import-Csv github_copilot_assessment_*.csv |
    Where-Object {$_.'Overall Copilot Status' -eq '✅ Pass'} |
    Measure-Object
```

**Bash Examples**:
```bash
# Extract failed repositories
awk -F',' '$15 ~ /❌/ {print $1}' github_security_assessment_*.csv

# Count Copilot-ready repositories
grep '✅ Pass' github_copilot_assessment_*.csv | wc -l
```

## API Rate Limits and Throttling

**GitHub API Rate Limits**:
- **Authenticated requests**: 5,000 requests per hour
- **Enterprise**: Higher limits depending on plan

**Built-in Rate Limiting**:
All scripts include:
- Automatic rate limit checking before requests
- Configurable threshold (default: 100 remaining requests)
- Automatic waiting when threshold reached
- Request delay between API calls (default: 0.05 seconds)

**Monitoring Rate Limits**:
```bash
# Check current rate limit status
gh api rate_limit
```

## Security Considerations

1. **Authentication**: Uses GitHub CLI authentication (no hardcoded tokens)
2. **Permissions**: Requires appropriate read permissions for assessments
3. **Sensitive Data**: CSV files excluded from git via `.gitignore`
4. **API Tokens**: No direct token management in code
5. **Error Handling**: Graceful degradation on permission errors

## Compliance and Frameworks

The assessments align with:
- **ISO 27001**: Information Security Management
- **FedRAMP**: Federal Risk and Authorization Management Program
- **SOC 2**: Service Organization Control
- **NIST**: Cybersecurity Framework

## Limitations

1. **Enterprise SSO**: Cannot query IdP settings directly for Enterprise orgs with Entra ID
2. **Private Repositories**: Requires appropriate access permissions
3. **Organization Access**: IDP assessment requires admin/owner role
4. **Rate Limits**: Large organizations may need longer execution times
5. **GitHub CLI Dependency**: Requires gh CLI installed and authenticated

## Future Enhancements

Potential improvements:
- [ ] Direct GitHub API integration (token-based)
- [ ] Historical trend analysis across multiple assessment runs
- [ ] Automated remediation suggestions with specific commands
- [ ] Integration with CI/CD pipelines for continuous assessment
- [ ] Dashboard visualization of assessment results
- [ ] Slack/Teams notifications for compliance issues
- [ ] Support for GitHub Enterprise Server (currently Cloud-only)
- [ ] Custom compliance framework definitions
- [ ] Automated report scheduling and archival

## Contributing

When contributing to this repository:

1. **Branch naming**: Use descriptive names (e.g., `feature/new-assessment-type`)
2. **Code style**: Follow existing patterns (CONFIG dict, parallel execution, error handling)
3. **Documentation**: Update both README.md and AGENTS.md
4. **Testing**: Test with small repository sets before full-scale runs
5. **CSV columns**: Maintain backward compatibility when possible
6. **Error handling**: Use try-except with informative error messages

## Additional Resources

- **GitHub CLI Documentation**: https://cli.github.com/manual/
- **GitHub API Documentation**: https://docs.github.com/en/rest
- **GitHub Advanced Security**: https://docs.github.com/en/code-security
- **GitHub Copilot Workspace**: https://docs.github.com/en/copilot
- **Python concurrent.futures**: https://docs.python.org/3/library/concurrent.futures.html

## Contact and Support

For issues or questions:
- Create an issue in the repository
- Contact the security team
- Refer to internal documentation

---

**Last Updated**: December 2024  
**Maintained by**: DevExpGbb Team  
**Target Audience**: LLM Coding Agents and AI Development Tools
