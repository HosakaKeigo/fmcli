# Contributing to fmcli

Contributions to fmcli are welcome!

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)

### Getting Started

```bash
# Clone the repository
git clone https://github.com/HosakaKeigo/fmcli.git
cd fmcli

# Install dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install
```

## Development Workflow

### 1. Check Issues

Before starting work, check for related issues. For new features or bug fixes, we recommend creating an issue first for discussion.

### 2. Create a Branch

```bash
git checkout -b issue-<number>/<brief-description>
```

### 3. Coding Standards

- **Formatter / Linter**: [ruff](https://docs.astral.sh/ruff/) (lint + format)
- **Type Checking**: [mypy](https://mypy.readthedocs.io/) (strict mode)
- **Testing**: [pytest](https://docs.pytest.org/)
- **Commit Messages**: [Conventional Commits](https://www.conventionalcommits.org/) format (in English)

### 4. Quality Gates

All of the following must pass before committing (also enforced by pre-commit hooks):

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -q
```

### 5. Pull Requests

- Follow the PR template
- Keep each PR focused on a single concern
- Add or update tests as needed

## Project Structure

```
src/fmcli/
├── cli/          # CLI command definitions (typer)
├── core/         # Error definitions, shared utilities
├── domain/       # Domain models (pydantic)
├── infra/        # External I/O (API client, storage)
├── services/     # Business logic
└── renderers/    # Output formatters
tests/
├── unit/         # Unit tests
└── integration/  # Integration tests
```

## Design Notes

- fmcli does not support delete operations — only create, read, and update
- Reflects the FileMaker Data API's **layout-centric model** directly
- **JSON is the canonical output**, with explainability via `--dry-run` / `--explain`

## Questions

Feel free to open an issue for any questions or discussions.
