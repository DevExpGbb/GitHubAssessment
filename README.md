# GitHub Enterprise Repository Best Practices Assessment Tool

A comprehensive tool for evaluating GitHub repositories against security best practices, compliance frameworks, and GitHub Copilot integration standards.

## Overview

This tool provides automated assessment of GitHub repositories to ensure they meet enterprise security requirements, compliance standards, and follow best practices for AI-assisted development with GitHub Copilot.

### Quick Links
- **For Developers**: See usage instructions below
- **For AI/LLM Agents**: See [AGENTS.md](AGENTS.md) for detailed technical documentation
- **Issue Tracker**: [GitHub Issues](https://github.com/DevExpGbb/GitHubAssessment/issues)

## Features

### 🤖 GitHub Copilot Best Practices Validation
Validates proper structure under `.github/` directory:

```
.github/
├── prompts/            # Task-specific prompts (.prompt.md)
├── instructions/       # Coding standards and best practices (.instructions.md)
├── agents/            # AI personas and specialized modes (.agent.md)
├── collections/       # Curated collections of related items (.collection.yml)
└── scripts/           # Utility scripts for maintenance
```

- **Task-Specific Prompts**: Include prompts organized by task in `.github/prompts/`
- **Coding Standards**: Document coding standards and best practices
- **AI Personas**: Create AI agents and specialized modes
- **Curated Collections**: Maintain curated collections of scripts and utilities
- **Mandatory Human Review**: Ensures human review is mandatory for Copilot-generated code
  - Example: Pull Request with manual approval required
- **Security Policies**: Validates policies to prevent generation of insecure code or licensing issues
  - Example: Block usage of unverified libraries


### 🔒 Security Controls Assessment
- **Code Scanning**: Validates that code scanning is enabled and checks for critical pending alerts
  - Example: Configure GitHub Advanced Security for continuous analysis
- **Secret Scanning**: Ensures active detection of exposed credentials
  - Example: Enable Secret Scanning in *Settings > Security & Analysis*
- **Dependabot Alerts**: Verifies configuration and monitors for outdated dependencies
  - Example: Enable automatic updates for vulnerable dependencies
- **Branch Protection**: Validates mandatory review requirements and status checks
  - Mandatory review before merge
  - Status checks applied (CI/CD, unit tests)

### 👥 Identity and Access Management
- **SSO Authentication**: Integration with corporate identity provider
- **MFA Enabled**: Requires multi-factor authentication for all users
- **Granular Permissions**: Audits specific permissions for teams and repositories
- **Environment Segregation**: Validates separation between production and test environments
- **Access Tokens Protection**: Reviews token and access key security
  - Periodic rotation required
  - Secure storage in vault (e.g., Azure Key Vault, HashiCorp Vault)

### 📊 Monitoring and Audit
- **Audit Logs**: Ensures logs are enabled with periodic review of records
- **Security Alerts**: Validates SIEM integration for security events
  - Example: Configure integration with Splunk or Azure Sentinel
- **Compliance Reporting**: Generates reports aligned with frameworks
  - ISO 27001: Information Security Management

## Getting Started

### Prerequisites

- Python 3.8+
- **GitHub CLI (gh)** installed and authenticated
- Virtual environment (recommended)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/DevExpGbb/GitHubAssessment.git
cd GitHubAssessment
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows PowerShell
# or
source .venv/bin/activate   # Linux/Mac
```

3. Install GitHub CLI (if not already installed):
```bash
# Windows
winget install --id GitHub.cli

# macOS
brew install gh

# Linux
# See https://cli.github.com/
```

4. Authenticate with GitHub CLI:
```bash
gh auth login
```
Follow the prompts to authenticate. Make sure you have appropriate permissions:
- Read access to repositories
- Access to security settings
- Organization owner/admin access (for IDP assessment)

### Configuration

Each assessment script has a `CONFIG` section at the top that you can customize:

```python
CONFIG = {
    'gh_command': 'gh',                    # GitHub CLI command
    'max_workers': 10,                     # Parallel execution threads
    'enable_rate_limit_check': True,       # Monitor API rate limits
    'rate_limit_threshold': 100,           # Warning threshold
    'request_delay': 0.05,                 # Delay between requests (seconds)
    'output_dir': '.',                     # Output directory for CSV files
    'verbose': True,                       # Detailed console output
}
```

## Usage

### 1. GitHub Copilot Best Practices Assessment

Validates Copilot-specific directory structure and configurations across all accessible repositories.

**Run the assessment:**
```bash
python assess_copilot_repos.py
```

**What it checks:**
- `.github/prompts/` directory with task-specific prompts (`.prompt.md` files)
- `.github/instructions/` with coding standards (`.instructions.md` files)
- `.github/agents/` with AI personas (`.agent.md` files)
- `.github/collections/` with curated collections (`.collection.yml` files)
- Proper file extensions and structure
- Repository metadata and accessibility

**Output:**
- Console summary per repository with pass/fail indicators
- CSV file: `github_copilot_assessment_YYYYMMDD_HHMMSS.csv`

**CSV Columns:**
- Repository details (name, owner, visibility)
- Directory existence checks (prompts, instructions, agents, collections)
- File count per directory
- Overall Copilot readiness status
- Recommendations for missing components

### 2. Security Assessment

Evaluates repository-level security controls across all accessible repositories.

**Run the assessment:**
```bash
python security_assessment.py
```

**What it checks:**
- Code Scanning (enabled, critical alerts)
- Secret Scanning (enabled, push protection, open alerts)
- Dependabot (enabled, open/critical alerts)
- Branch Protection (enabled, rulesets vs legacy, review requirements)
- Organization default settings for new repositories

**Output:**
- Console summary with statistics and recommendations
- CSV file: `github_security_assessment_YYYYMMDD_HHMMSS.csv`

**CSV Columns:**
- Repository details (name, owner, type, visibility)
- Security control status (enabled/disabled, pass/fail)
- Alert counts (critical, open)
- Organization defaults for new repositories
- Overall security compliance status
- Error details (if any)

### 3. Identity & Access Management (IDP) Assessment

Evaluates organization-level identity, authentication, and access controls.

**Run the assessment:**
```bash
python idp_assessment.py
```

**What it checks:**
- SSO/OIDC configuration (Enterprise-level authentication)
- 2FA requirements (org-level or IdP-managed)
- Granular permissions (default repository permissions)
- Environment segregation (deployment environments usage)
- Token security (Advanced Security, Secret Scanning for new repos, Dependabot)

**Output:**
- Console summary with compliance status and recommendations
- CSV file: `github_idp_assessment_YYYYMMDD_HHMMSS.csv`

**CSV Columns:**
- Organization details (name, plan, enterprise status)
- SSO/Authentication status (2FA, Enterprise SSO, IP restrictions)
- Permission settings (default access, member capabilities)
- Environment usage statistics
- Token security configurations
- Overall IAM compliance status
- Verification instructions for Enterprise SSO

**Note:** Requires organization owner or admin access. For Enterprise organizations using Entra ID (Azure AD), the tool provides verification instructions to check SSO/OIDC configuration in the Azure Portal.

### Understanding CSV Output Files

All assessment scripts generate timestamped CSV files that are automatically saved to the current directory (or configured `output_dir`).

**File naming pattern:**
```
github_{assessment_type}_assessment_{timestamp}.csv
```

**Examples:**
- `github_security_assessment_20251201_143052.csv`
- `github_idp_assessment_20251201_143123.csv`
- `github_copilot_assessment_20251201_143145.csv`

**Working with CSV files:**

```bash
# View in Excel/Sheets
start github_security_assessment_20251201_143052.csv  # Windows
open github_security_assessment_20251201_143052.csv   # macOS

# View in terminal (Linux/macOS/Windows with WSL)
csvlook github_security_assessment_20251201_143052.csv

# Filter and analyze with PowerShell
Import-Csv github_security_assessment_20251201_143052.csv | 
    Where-Object {$_.'Overall Security Status' -eq '❌ Fail'} | 
    Select-Object Repository, 'Code Scanning Enabled', 'Secret Scanning Enabled'

# Convert to JSON for programmatic processing
Import-Csv github_security_assessment_20251201_143052.csv | 
    ConvertTo-Json | 
    Out-File results.json
```

**CSV files are excluded from git** (via `.gitignore`) to prevent accidental commit of sensitive assessment data.

## Assessment Checklist

### ✅ Security Controls
- [ ] Code Scanning enabled with no critical alerts
- [ ] Secret Scanning active
- [ ] Dependabot Alerts configured
- [ ] Branch Protection Rules applied

### ✅ Identity & Access
- [ ] SSO and MFA enabled
- [ ] Granular permissions configured
- [ ] Environment segregation implemented
- [ ] Tokens and keys protected

### ✅ Monitoring & Audit (not covered in scripts yet)
- [ ] Audit logs enabled and reviewed
- [ ] Security alerts integrated with SIEM
- [ ] Compliance reports generated

### ✅ Copilot Best Practices
- [ ] `.github/prompts/` directory with task-specific prompts
- [ ] `.github/instructions/` with coding standards documented
- [ ] `.github/agents/` with AI personas and specialized modes
- [ ] `.github/collections/` with curated collections
- [ ] `.github/scripts/` with utility scripts
- [ ] Human review mandatory for AI-generated code (Pull Request approval)
- [ ] Security policies enforced (block unverified libraries)

## Compliance Frameworks

This tool supports assessment alignment with:
- **ISO 27001**: Information Security Management
- **FedRAMP**: Federal Risk and Authorization Management Program
- **SOC 2**: Service Organization Control
- **NIST**: National Institute of Standards and Technology guidelines

## Project Structure

```
GitHubAssessment/
├── security_assessment.py           # Repository security controls assessment
├── idp_assessment.py                # Identity & access management assessment
├── assess_copilot_repos.py          # GitHub Copilot best practices validation
├── list_repos_gh_cli.py            # Repository listing utility
├── list_repos_gh_cli_optimized.py  # Optimized repository listing
├── list_and_check_repos.py         # Combined listing and checking
├── MCP/                            # Model Context Protocol configurations
├── .venv/                          # Python virtual environment
├── .gitignore                      # Excludes .venv, CSV files, logs
├── github_security_assessment_*.csv     # Generated security reports
├── github_idp_assessment_*.csv          # Generated IDP reports
├── github_copilot_assessment_*.csv      # Generated Copilot reports
├── README.md                       # This file - Human-readable documentation
└── AGENTS.md                       # LLM/AI agent documentation for code assistance
```

## Output and Reports

### Console Output
Each assessment script provides:
- **Progress indicators** with emoji status symbols
- **Real-time statistics** (repositories processed, rate limit status)
- **Summary section** with adoption percentages
- **Compliance scores** and recommendations
- **Non-compliant items** list (first 10 items shown)
- **Performance metrics** (fetch time, assessment time, total time)

### CSV Reports
All assessments generate timestamped CSV files with:
- **Detailed per-item analysis** (repository or organization)
- **Status columns** (✅ Pass / ❌ Fail / ⚠️ Review)
- **Quantitative metrics** (alert counts, percentages)
- **Error tracking** (issues encountered during assessment)
- **Compliance indicators** (overall status per item)

### Report Retention
- CSV files are **excluded from version control** (see `.gitignore`)
- Files persist locally for historical tracking
- Timestamp format: `YYYYMMDD_HHMMSS` for easy sorting
- Recommended: Archive old reports periodically

## Best Practices

### Running Assessments

**Frequency:**
- **Security Assessment**: Weekly for active repositories, monthly for stable ones
- **IDP Assessment**: Monthly or after organization configuration changes
- **Copilot Assessment**: After onboarding new repositories or teams

**Workflow:**
```bash
# 1. Activate virtual environment
.venv\Scripts\Activate.ps1

# 2. Run assessments in sequence (recommended order)
python assess_copilot_repos.py      # 1st: Check Copilot readiness
python security_assessment.py       # 2nd: Check repository security
python idp_assessment.py            # 3rd: Check organization IAM

# 3. Review CSV outputs
# Sort files by timestamp to find latest reports
Get-ChildItem *.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 3
```

**Rate Limiting:**
- Scripts automatically monitor GitHub API rate limits
- Configurable thresholds and delays in `CONFIG` section
- For large organizations (100+ repos), consider running during off-peak hours

### For Repository Owners
1. **Enable security controls** before running assessment
   - Code Scanning (GitHub Advanced Security)
   - Secret Scanning with Push Protection
   - Dependabot alerts and security updates
2. **Configure branch protection** for main/production branches
   - Require pull request reviews
   - Require status checks to pass
   - Consider using Repository Rulesets (recommended over legacy rules)
3. **Implement `.github/` structure** for Copilot integration
4. **Schedule regular assessments** and track improvements over time

### For Security Teams
1. **Establish baseline scores** from initial assessment
2. **Track remediation progress** using timestamped CSV files
3. **Compare reports over time** to measure security posture improvements
4. **Prioritize critical issues**:
   - Repositories with open critical alerts
   - Public repositories without secret scanning
   - Production repositories without branch protection
5. **Generate compliance reports** by filtering CSV data by organization/team

### For Development Teams
1. **Review assessment results** for your repositories
2. **Address failing checks** before requesting reviews
3. **Follow Copilot guidelines** in `.github/prompts/` and `.github/instructions/`
4. **Ensure human review** for AI-generated code via pull request approvals
5. **Report assessment issues** (false positives, permission problems) to security team

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request with clear description

### For AI/LLM Developers

If you're working with LLM coding agents or AI-powered development tools, see **[AGENTS.md](AGENTS.md)** for:
- Detailed codebase architecture and patterns
- Development guidelines and conventions
- API endpoint documentation
- Testing and validation procedures
- Common issues and solutions
- Code modification examples

## License

[Specify License]

## Support

For issues or questions:
- Create an issue in the repository
- Contact the security team
- Refer to internal documentation

## Troubleshooting

### GitHub CLI Authentication Issues
```bash
# Check authentication status
gh auth status

# Re-authenticate if needed
gh auth login

# Test API access
gh api user
```

### Rate Limit Issues
```bash
# Check current rate limit
gh api rate_limit

# Solution 1: Reduce parallel workers in CONFIG
'max_workers': 5  # Lower from default 10-15

# Solution 2: Increase request delay
'request_delay': 0.1  # Increase from default 0.05

# Solution 3: Disable rate limit checking (not recommended)
'enable_rate_limit_check': False
```

### Permission Issues
**Security Assessment:**
- Requires read access to repositories
- Needs access to security settings (Code Scanning, Secret Scanning)

**IDP Assessment:**
- Requires organization owner or admin role
- Enterprise organizations: Cannot query IdP settings directly (manual verification needed)

**Solution:**
```bash
# Verify your organization role
gh api user/orgs

# Request elevated permissions from organization admin
```

### Empty or No Results
```bash
# Check repository access
gh repo list --limit 5

# Check organization access
gh api user/orgs

# Verify CLI configuration
gh config list
```

## Performance Tips

**For Large Organizations (100+ repositories):**
1. Run assessments during off-peak hours to minimize rate limit impact
2. Adjust parallel workers based on your API rate limit tier:
   - Free tier: `max_workers: 5`
   - Pro/Team: `max_workers: 10`
   - Enterprise: `max_workers: 15-20`
3. Enable verbose output for troubleshooting: `'verbose': True`
4. Consider filtering specific organizations or repositories

**Typical Execution Times:**
- **Security Assessment**: 0.2-0.5s per repository (parallel execution)
- **IDP Assessment**: 5-10s per organization
- **Copilot Assessment**: 0.1-0.3s per repository

**Example Performance (100 repositories):**
- Repository fetch: 3-5 seconds
- Security assessment: 30-60 seconds
- Total execution: 35-65 seconds

## Roadmap

- [x] Security assessment with parallel execution
- [x] IDP assessment with Enterprise SSO support
- [x] Copilot best practices validation
- [x] CSV export with timestamped files
- [ ] Advanced analytics dashboard
- [ ] Trend analysis across multiple assessments
- [ ] Custom compliance framework definitions
- [ ] Automated remediation suggestions
- [ ] Integration with CI/CD pipelines
- [ ] Slack/Teams notifications for compliance issues
- [ ] Support for GitHub Enterprise Server (currently supports Cloud)

## Acknowledgments

Built to support enterprise GitHub security and AI-assisted development best practices.

**Key Technologies:**
- GitHub CLI (gh) for authenticated API access
- Python ThreadPoolExecutor for parallel assessment
- GitHub Advanced Security features
- Repository Rulesets (next-gen branch protection)

---

**Last Updated**: December 2025  
**Version**: 1.0  
**Supported GitHub Plans**: Free, Pro, Team, Enterprise Cloud
