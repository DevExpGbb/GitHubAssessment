# GitHub Enterprise Repository Risk Assessment Tool

A comprehensive tool for evaluating GitHub repositories against security best practices, compliance frameworks, and GitHub Copilot integration standards.

## Overview

This tool provides automated assessment of GitHub repositories to ensure they meet enterprise security requirements, compliance standards, and follow best practices for AI-assisted development with GitHub Copilot.

## Features

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
  - FedRAMP: Federal Risk and Authorization Management Program

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

## Getting Started

### Prerequisites

- Python 3.8+
- GitHub Personal Access Token with appropriate permissions
- Virtual environment (recommended)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd GHEreporassessment
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
# or
source .venv/bin/activate   # Linux/Mac
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Configuration

1. Set up your GitHub token as an environment variable:
```bash
$env:GITHUB_TOKEN = "your_token_here"  # Windows PowerShell
# or
export GITHUB_TOKEN="your_token_here"  # Linux/Mac
```

2. Configure assessment parameters in `config.yml` (if applicable)

## Usage

### Quick Start

Run the assessment tool:
```bash
python one_stopscript.py
```

### Check Copilot Directory Structure

Validate Copilot best practices:
```bash
python check_copilot_dirs.py
```

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

### ✅ Monitoring & Audit
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
GHEreporassessment/
├── check_copilot_dirs.py    # Copilot structure validation
├── one_stopscript.py         # Main assessment script
├── MCP/                      # Model Context Protocol configurations
├── .venv/                    # Python virtual environment
└── README.md                 # This file
```

## Output and Reports

Assessment results are generated in the following formats:
- Console output with color-coded results
- JSON reports for programmatic processing
- HTML reports for stakeholder review
- CSV exports for compliance tracking

## Best Practices

### For Repository Owners
1. Enable all native security controls before running assessment
2. Configure branch protection rules for critical branches
3. Implement `.github/` directory structure for Copilot
4. Schedule regular assessments (weekly/monthly)

### For Security Teams
1. Integrate assessment results with existing SIEM
2. Establish baseline security scores for repositories
3. Track remediation of identified issues
4. Review audit logs regularly

### For Development Teams
1. Follow Copilot prompt guidelines in `.github/prompts/`
2. Adhere to coding standards in `.github/instructions/`
3. Request human review for AI-generated code
4. Report false positives to security team

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request with clear description

## License

[Specify License]

## Support

For issues or questions:
- Create an issue in the repository
- Contact the security team
- Refer to internal documentation

## Roadmap

- [ ] Support for GitHub Enterprise Cloud/Server
- [ ] Advanced analytics dashboard
- [ ] Custom compliance framework definitions
- [ ] Automated remediation suggestions
- [ ] Integration with CI/CD pipelines

## Acknowledgments

Built to support enterprise GitHub security and AI-assisted development best practices.

---

**Last Updated**: November 2025  
**Version**: MVP 1.0
