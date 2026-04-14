# fmcli

![Python](https://img.shields.io/badge/python-3.12%2B-blue)

FileMaker Data API CLI wrapper.

FileMaker Data API CLI wrapper.

## Installation

### Prerequisites

- Python 3.12+
- Access to GitHub (`gh auth login` completed or SSH configured)

### Option 1: uv tool (recommended)

If [uv](https://docs.astral.sh/uv/) is installed, you can install with a single command:

```bash
uv tool install git+https://github.com/HosakaKeigo/fmcli.git
```

### Option 2: pipx

```bash
pipx install git+https://github.com/HosakaKeigo/fmcli.git
```

### Upgrade

```bash
# uv tool
uv tool upgrade fmcli

# pipx
pipx upgrade fmcli
```

### Uninstall

```bash
# uv tool
uv tool uninstall fmcli

# pipx
pipx uninstall fmcli
```

## Usage

```bash
fmcli --help
```

### Initial Setup

```bash
# Configure connection via interactive wizard
fmcli auth config

# Login
fmcli auth login
```

### Basic Workflow

```bash
# 1. Check field names (always run before searching)
fmcli schema find-schema -l 'LayoutName'

# 2. Search records
fmcli record find -l 'LayoutName' -q '{"FieldName":"value"}'

# 3. Check field types and attributes as needed
fmcli layout describe -l 'LayoutName'
```

## Environment Variables

fmcli supports the following environment variables, used as fallbacks when command-line options are not specified.

| Variable | Description | Example |
|----------|-------------|---------|
| `FMCLI_HOST` | FileMaker Server host URL. Used when `--host` is not specified | `https://fm.example.com` |
| `FMCLI_DATABASE` | Database name. Used when `-d` is not specified and `FMCLI_HOST` is set | `MyDatabase` |
| `FMCLI_ALLOW_INSECURE_HTTP` | Set to `1` or `true` to allow HTTP connections. Used when `--allow-insecure-http` is not specified | `1` |
| `NO_COLOR` | Disables color output when set ([no-color.org](https://no-color.org/) compliant) | `1` |
| `XDG_CONFIG_HOME` | Base directory for config files. Defaults to `~/.config` | `~/.config` |
| `XDG_CACHE_HOME` | Base directory for cache files. Defaults to `~/.cache` | `~/.cache` |

### Resolution Priority

Profiles (connection targets) are resolved in the following order:

1. `--host` + `-d` (command-line options)
2. `FMCLI_HOST` + `FMCLI_DATABASE` (environment variables)
3. Default profile (`default_profile_key` in `~/.config/fmcli/config.json`)

### File Locations

| Path | Contents |
|------|----------|
| `$XDG_CONFIG_HOME/fmcli/config.json` | Default profile configuration |
| `$XDG_CONFIG_HOME/fmcli/profiles/` | Profile files (per host/database) |
| `$XDG_CACHE_HOME/fmcli/` | Cache |

## Output Format

All commands output in **Envelope** format. The default is JSON (`stdout`), with errors sent to `stderr`. Use `--format table` to display list data as tables (unsupported data types automatically fall back to JSON).

### Success Response

```json
{
  "ok": true,
  "command": "record find",
  "profile": "https://fm.example.com|MyDatabase",
  "database": "MyDatabase",
  "layout": "Customers",
  "data": [ ... ],
  "pagination": {
    "offset": 1,
    "limit": 100,
    "total_count": 42
  },
  "messages": [],
  "api": {
    "method": "POST",
    "url": "https://fm.example.com/fmi/data/vLatest/databases/MyDatabase/layouts/Customers/_find",
    "duration_ms": 234.5
  }
}
```

### Error Response

```json
{
  "ok": false,
  "command": "record find",
  "error": {
    "type": "api_error",
    "message": "FileMaker API error: Layout not found (api_code: 105)",
    "http_status": 500,
    "api_code": 105,
    "retryable": false,
    "hint": "Check layout name: fmcli layout list",
    "host": "https://fm.example.com",
    "database": "MyDatabase"
  }
}
```

### Envelope Fields

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` | `true` on success, `false` on error |
| `command` | `string` | Executed command name (e.g., `record find`) |
| `profile` | `string` | Profile key used |
| `database` | `string` | Target database name |
| `layout` | `string` | Target layout name |
| `data` | `any` | Command result data |
| `pagination` | `object\|null` | Pagination info (`offset`, `limit`, `total_count`) |
| `api` | `object\|null` | API call info (`method`, `url`, `duration_ms`) |
| `messages` | `string[]` | Messages from FileMaker Server |
| `script_results` | `object\|null` | Script execution results (if applicable) |
| `error` | `object\|null` | Error details (only when `ok: false`) |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `41` | Authentication error |
| `42` | Input error |
| `43` | Transport error |
| `44` | FileMaker API error |
| `51` | Configuration error |
| `52` | Resource not found |
| `130` | User interrupt (Ctrl+C) |

## Shell Completion

fmcli supports shell completion. Use the following commands to set up completion for your shell:

```bash
# Install completion (auto-detects bash / zsh / fish / PowerShell)
fmcli --install-completion

# Show completion script (for manual setup)
fmcli --show-completion
```

After installation, restart your shell to enable completion. Supports completion for command names, option names, layout names, host names, and database names.

## Troubleshooting

### fmrest Extended Access Privilege

To use the FileMaker Data API, the **fmrest extended access privilege** must be enabled on the FileMaker Server side.

1. Open the target file in FileMaker Pro
2. Go to **File > Manage > Security**
3. Add **fmrest** to the extended access privileges for the target privilege set
4. Verify the file is hosted on FileMaker Server Admin Console

If fmrest is not enabled, the following error is returned:

```
API error code 959: FileMaker Data API is disabled. Contact your server administrator.
```

### HTTPS Requirements and HTTP Connections

fmcli requires HTTPS connections by default. To allow HTTP connections (e.g., in development environments), use one of the following:

```bash
# Command-line option
fmcli auth login --host http://localhost --allow-insecure-http

# Environment variable
export FMCLI_ALLOW_INSECURE_HTTP=1
```

> **Warning**: Always use HTTPS in production environments. HTTP connections transmit passwords and session tokens in plain text.

### Session Expiration and Auto-Refresh

FileMaker Data API sessions expire after 15 minutes of inactivity by default. fmcli detects expired sessions and automatically attempts re-authentication using credentials stored in the keyring.

- **Auto-refresh requires**: Password saved to keyring during `fmcli auth login`
- **Manual re-authentication**: Run `fmcli auth login` again

### Common Error Codes

| API Code | Meaning | Solution |
|----------|---------|----------|
| `100` / `101` | Record not found | Verify the record ID |
| `105` | Layout not found | Check layout name with `fmcli layout list` |
| `401` | Field not found | Check field name with `fmcli schema find-schema -l <layout>` |
| `402` | No records match the query | Review your query |
| `952` | Session expired | Auto-refreshes if keyring is configured. Manual: `fmcli auth login` |
| `953` | Invalid session | Re-login with `fmcli auth login` |
| `954` | Max concurrent connections | Wait and retry |
| `958` | Data API license error | Check FileMaker Server configuration |
| `959` | Data API disabled | Contact server administrator |

### Network Connection Errors

If you cannot connect, verify the following:

- Host name and port are correct: `fmcli auth status`
- FileMaker Server is running
- Port 443 (HTTPS) is open in the firewall

## Agent Skills

A skill is included for using fmcli with Claude Code, providing automatic command reference.

### Installation via Vercel Skills

Using [Vercel Skills](https://skills.sh/):

```bash
npx skills add https://github.com/HosakaKeigo/fmcli
```

### Update

```bash
npx skills update https://github.com/HosakaKeigo/fmcli
```

### Manual Installation

```bash
# Copy the .claude/skills from the repository to ~/.claude/skills
cp -r .claude/skills/fmcli-guide ~/.claude/skills/fmcli-guide
```

Once installed, Claude Code will automatically reference the correct commands and options when working with fmcli.

## Development

### Setup

```bash
git clone https://github.com/HosakaKeigo/fmcli.git
cd fmcli
uv sync
```

### Commands

```bash
uv run ruff check .           # lint
uv run ruff format --check .  # format check
uv run mypy src               # type check
uv run pytest -q              # test
```
