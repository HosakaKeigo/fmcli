# Changelog

Based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-04-15

### Added

- **Write operations** (`record create/update/upload`)
  - `record create` — create records with confirmation prompt and field validation
  - `record update` — update records with optimistic locking (`--mod-id`), auto diff, and undo backup
  - `record upload` — upload files to container fields (multipart/form-data)
  - All write commands support `--dry-run`, `--yes`, and `--skip-field-check`
- **Global config** (`config set/get/list/unset`)
  - Configurable API timeout
- **Environment variable support** (`FMCLI_HOST`, `FMCLI_DATABASE`, `FMCLI_ALLOW_INSECURE_HTTP`)
- **Default profile resolution** — env vars and `config.json` fallback
- **Shell completion** — bash / zsh / fish / PowerShell

## [0.1.0] - 2026-03-20

Initial release of the FileMaker Data API CLI wrapper.

### Added

- **Authentication** (`auth login/logout/status/list/config`)
  - Secure credential management via OS keyring
  - Automatic session refresh (`call_with_refresh`)
  - Non-interactive login with `--password-stdin`
  - Interactive setup wizard (`auth config`)
- **Profiles** (`profile list/show`)
  - Implicit resolution via default profile
  - Auto-generated on `auth login`
- **Metadata** (`host info`, `database list`, `layout list/describe`, `script list`)
  - Filtering with `layout list --filter`
  - Value list retrieval (`layout describe --value-lists`)
- **Records** (`record get/list/find`)
  - JSON query search (`-q` / `-f`)
  - Sort and pagination (`--sort`, `--limit`, `--offset`)
  - Client-side field filtering (`--fields`)
  - Portal data retrieval (`--portal`)
  - `--first` / `--count` / `--with-schema` options
- **Explainability** (`explain find`, `schema find-schema/output`)
  - Request preview with `--dry-run`
  - Field search with `schema find-schema --filter --type`
- **Output** — JSON / table format (`--format json|table`)
- **Security**
  - HTTPS enforced by default (HTTP requires explicit opt-in)
  - Script execution opt-in only
  - Atomic session file writes with symlink rejection
  - Structured logging with `--verbose`
- **Cross-platform** — macOS / Windows support
- **Shell completion** — bash / zsh / fish / PowerShell
- **CI** — Parallel lint / typecheck / test jobs, security scanning, Dependabot
- **OSS** — MIT License

### Security

- Mask tokens in API response URLs on logout (#4)
- Implement secure session token storage (#3)
- Warn on credential persistence failure during login (#18)
