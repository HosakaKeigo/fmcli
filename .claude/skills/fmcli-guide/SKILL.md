---
name: fmcli-guide
description: >
  Usage guide for FileMaker CLI (fmcli). Always refer to this before executing fmcli commands.
  Trigger when:
  (1) about to execute an fmcli command
  (2) fetching data from FileMaker Data API
  (3) looking up layouts, records, or fields in FileMaker
  (4) user asks about fmcli
---

# fmcli Usage Guide

**Use only the commands and options listed here. Do not guess or invent commands.**

## Typical Workflow

```bash
# 1. Check available layout names
fmcli layout list

# 2. Check searchable field names (always run before searching)
fmcli schema find-schema -l 'LayoutName'

# 3. Search records (use field names confirmed in step 2)
fmcli record find -l 'LayoutName' -q '{"FieldName":"value"}'
```

## Command Reference (no other commands exist)

### Authentication

```
fmcli auth config                  # Interactive setup wizard (recommended for first use)
fmcli auth login --host URL -d DB  # Login to a specific host/database
fmcli auth logout                  # Logout
fmcli auth status                  # Check authentication status
fmcli auth list                    # List all sessions
```

### Metadata

```
fmcli layout list                       # List layouts
fmcli layout describe -l 'LayoutName'   # Show field structure and types
fmcli database list                     # List databases
fmcli host info                         # Show host information
fmcli script list                       # List scripts
```

### Record Operations (Read)

```
fmcli record get RECORD_ID -l 'LayoutName'
fmcli record list -l 'LayoutName' [--limit N] [--offset N] [--sort 'Field:ascend']
fmcli record find -l 'LayoutName' -q '{"Field":"value"}' [--limit N] [--first] [--count]
```

### Record Operations (Write)

**Check fields first (`schema find-schema`). For `update`/`upload`, inspect the target record first.**

```
# Create a record
fmcli record create -l 'LayoutName' --field-data '{"Field":"value"}' [--yes] [--dry-run] [--skip-field-check]
# Alternative: read field data from file
fmcli record create -l 'LayoutName' -f data.json [--yes] [--dry-run]

# Update a record (requires current modId)
fmcli record update RECORD_ID -l 'LayoutName' --field-data '{"Field":"new value"}' --mod-id MOD_ID [--yes] [--dry-run] [--no-backup] [--skip-field-check]
# Alternative: read field data from file
fmcli record update RECORD_ID -l 'LayoutName' -f changes.json --mod-id MOD_ID [--yes] [--dry-run]

# Upload a file to a container field
fmcli record upload RECORD_ID -l 'LayoutName' --field 'ContainerField' --file /path/to/file [--yes] [--dry-run] [--repetition N] [--if-mod-id MOD_ID] [--skip-field-check]
```

**Note:** `-f` is `--field-data-file` (for create/update), NOT `--field-data`. In `record find`, `-f` means `--query-file`.

**Required workflow for `record update`:**
1. Run `record get` or `record find` to fetch the target record.
2. Read `modId` from the response.
3. Run `record update ... --mod-id MOD_ID ...`.

**Safety rules:**
- In non-interactive usage (pipes, AI agents), all write commands require `--yes`.
- Prefer `--dry-run` first to review the request before executing.
- `record create` validates field names against the layout before writing.
- `record upload` validates that the target field is a container type.
- `record update` automatically saves undo information (backup) unless `--no-backup` is specified.
- `--skip-field-check` bypasses validation — use only when necessary.

### Field Information

```
fmcli schema find-schema -l 'LayoutName'  # List searchable fields
fmcli schema output -l 'LayoutName'       # Show layout output structure
```

### Query Explanation

```
fmcli explain find -l 'LayoutName' -q '{"Field":"value"}'
```

### Profiles

```
fmcli profile list   # List saved profiles
fmcli profile show   # Show default profile details
```

## record find — Detailed Options

| Option | Description |
|--------|-------------|
| `-l`, `--layout` | Layout name (required) |
| `-q`, `--query` | Search query JSON (`-q` or `-f` is required) |
| `-f`, `--query-file` | Search query JSON file (alternative to `-q`) |
| `--limit` | Number of records to return (default: 100) |
| `--offset` | Starting position (default: 1) |
| `--sort`, `-s` | Sort order (e.g., `Name:ascend`) |
| `--fields` | Filter output fields (client-side only; does not reduce API payload) |
| `--portal`, `-p` | Portal specification (e.g., `Portal1:10`) |
| `--first` | Return only the first record |
| `--count` | Return only the record count |
| `--with-schema` | Include field schema in response |
| `--dry-run` | Show request details without executing |

## Common Mistakes

- `fmcli schema fields` → Does not exist. Use `fmcli schema find-schema -l ...`
- `fmcli layout fields` → Does not exist. Use `fmcli layout describe -l ...`
- `fmcli record search` → Does not exist. Use `fmcli record find -l ... -q ...`
- `fmcli record find -q ...` without `-l` → `-l` (layout name) is required
- Searching without checking field names → Always run `schema find-schema` first
- `record update` without `--mod-id` → Must first run `record get`/`find` to obtain modId
- Write commands without `--yes` in non-interactive mode → All write ops require `--yes`
- Updating with a stale modId → Fetch the record again before retrying
- Uploading to a non-container field → `record upload` only works with container fields

## Global Options

| Option | Description |
|--------|-------------|
| `--format json\|table` | Output format (default: json) |
| `--verbose` | Include API info and pagination in output |
| `--install-completion` | Install shell completion |
| `--show-completion` | Show shell completion script |

To disable colors: set `NO_COLOR=1` environment variable ([no-color.org](https://no-color.org/) compliant).

> **Tip**: There is no `--output-file` option. Use shell pipes and redirects to save or process output:
> ```bash
> fmcli record find -l 'Layout' -q '{"Field":"value"}' > result.json       # Save to file
> fmcli record find -l 'Layout' -q '{"Field":"value"}' | jq '.data[]'      # Process with jq
> fmcli record find -l 'Layout' -q '{"Field":"value"}' | python3 script.py # Pipe to Python
> ```

## Specifying Connection Target

If a default profile is configured, `--host` / `-d` are not needed.
Only specify them when using a different database:

```bash
fmcli layout list --host https://fm.example.com -d 'DatabaseName'
```

## FileMaker-Specific Notes

- Date format: `MM/DD/YYYY` (e.g., `03/11/2026`)
- Layout and field names may contain Japanese characters or full-width spaces
- Query JSON supports FileMaker search operators (e.g., `==` exact match, `>` greater than)
