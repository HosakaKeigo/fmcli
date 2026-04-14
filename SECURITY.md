# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not create a public issue**. Instead, report it directly via email:

Open a [GitHub Security Advisory](https://github.com/HosakaKeigo/fmcli/security/advisories/new) on this repository.

Please include the following in your report:

- Description of the vulnerability
- Steps to reproduce
- Estimated impact

We will acknowledge receipt within **5 business days**.

## Security Design Principles

- fmcli does not support delete operations — only create, read, and update
- Credentials are stored in the OS **keyring** (macOS Keychain / Windows Credential Manager, etc.)
- Session tokens are cached on the filesystem, scoped to the user's home directory
- Communication with FileMaker Server assumes **HTTPS**
