# Security Policy

## Overview

This document outlines the security practices, policies, and procedures for the Azure FinOps MCP Server project.

## Security Features

### Authentication & Authorization
- ✅ Uses Azure SDK's `DefaultAzureCredential` for secure authentication
- ✅ Supports multiple authentication methods (Azure CLI, Managed Identity, Environment)
- ✅ No hardcoded credentials in codebase
- ✅ All sensitive configuration via environment variables

### Secure Communication
- ✅ HTTPS enforced for all Azure API calls
- ✅ Certificate validation enabled by default
- ✅ Token-based authentication with automatic refresh

### Rate Limiting
- ✅ Token bucket algorithm implementation
- ✅ Configurable per-subscription limits
- ✅ Burst capacity for legitimate traffic spikes
- ✅ Default: 10 requests/second with burst of 20

### Secret Management
- ✅ Pre-commit hooks for secret detection
- ✅ `.secrets.baseline` for tracking allowed patterns
- ✅ Environment variables for all sensitive data
- ✅ No secrets in version control

### Dependency Security
- ✅ Locked dependencies in `requirements-locked.txt`
- ✅ Automated vulnerability scanning in CI/CD
- ✅ Multiple scanners: Trivy, pip-audit, safety
- ✅ Regular Bandit security linting

## Security Best Practices

### For Contributors

1. **Never commit secrets**
   - Use environment variables for sensitive data
   - Run `detect-secrets scan` before committing
   - Pre-commit hooks will catch most issues

2. **Validate all inputs**
   - Sanitize subscription IDs and resource names
   - Use the validators in `helpers/validators.py`
   - Never pass user input directly to subprocess

3. **Handle errors securely**
   - Don't expose internal details in error messages
   - Log security events appropriately
   - Use structured logging for audit trails

4. **Follow secure coding standards**
   - Use parameterized queries (no string concatenation)
   - Validate and sanitize all external data
   - Apply principle of least privilege

### For Users

1. **Credential Security**
   ```bash
   # Use Azure CLI authentication (recommended)
   az login

   # Or use environment variables
   export AZURE_SUBSCRIPTION_ID=your-subscription-id
   export AZURE_TENANT_ID=your-tenant-id
   export AZURE_CLIENT_ID=your-client-id
   export AZURE_CLIENT_SECRET=your-client-secret  # Use secret management tools
   ```

2. **Rate Limiting Configuration**
   ```bash
   # Adjust rate limits based on your needs
   export AZURE_RATE_LIMIT_ENABLED=true
   export AZURE_RATE_LIMIT_REQUESTS_PER_SECOND=10
   export AZURE_RATE_LIMIT_BURST_SIZE=20
   ```

3. **Secure Deployment**
   - Run in isolated environment
   - Use managed identities when possible
   - Enable audit logging
   - Monitor for anomalous activity

## Vulnerability Reporting

### Reporting Process

1. **DO NOT** create public GitHub issues for security vulnerabilities
2. Email security concerns to: [security@your-domain.com]
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 5 business days
- **Resolution Target**: Based on severity
  - Critical: 24 hours
  - High: 7 days
  - Medium: 30 days
  - Low: Next release

## Security Scanning

### Automated Scans

The project uses multiple security scanning tools:

- **Bandit**: Python security linting
- **Trivy**: Comprehensive vulnerability scanner
- **pip-audit**: Python dependency vulnerabilities
- **safety**: Known security issues in dependencies
- **detect-secrets**: Pre-commit secret detection

### Manual Security Review

Run security scan locally:

```bash
# Install security tools
pip install bandit safety pip-audit detect-secrets

# Run Bandit
bandit -r azure_finops_mcp_server/

# Check dependencies
pip-audit
safety check

# Scan for secrets
detect-secrets scan --baseline .secrets.baseline
```

## Compliance

### Data Protection
- No PII storage in logs or cache
- Minimal data retention
- Secure data transmission only

### Azure Best Practices
- Follows Azure SDK security guidelines
- Implements Azure Well-Architected Framework security pillar
- Compliant with Azure security baseline

## Security Updates

### Update Schedule
- **Critical patches**: Immediately
- **Security updates**: Weekly
- **Dependency updates**: Monthly
- **Full security audit**: Quarterly

### Staying Informed
- Monitor GitHub Security Advisories
- Subscribe to Azure Security Center alerts
- Review dependency changelogs

## Security Checklist

### Before Each Release
- [ ] Run full security scan
- [ ] Update dependencies
- [ ] Review security advisories
- [ ] Test rate limiting
- [ ] Verify no secrets in code
- [ ] Update security documentation

### For New Features
- [ ] Threat model the feature
- [ ] Add input validation
- [ ] Implement rate limiting
- [ ] Add security tests
- [ ] Document security considerations

## Security Architecture

### Defense in Depth
```
Layer 1: Authentication (Azure AD)
  ↓
Layer 2: Authorization (RBAC)
  ↓
Layer 3: Rate Limiting (Token Bucket)
  ↓
Layer 4: Input Validation (Validators)
  ↓
Layer 5: Secure Communication (HTTPS)
  ↓
Layer 6: Error Handling (Safe Errors)
  ↓
Layer 7: Logging & Monitoring (Audit Trail)
```

## Contact

For security concerns, contact:
- Security Team: [security@your-domain.com]
- Project Maintainers: See MAINTAINERS.md

## Acknowledgments

We appreciate responsible disclosure of security vulnerabilities.
Contributors who report valid security issues will be acknowledged in our security hall of fame.

---

*Last Updated: 2025-09-09*
*Next Review: 2025-12-09*
