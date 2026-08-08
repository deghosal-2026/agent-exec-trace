# Contributing

Contributions are welcome! Here's how to get started.

## Bug Reports

Submit bugs via [GitHub Issues](https://github.com/deghosal-2026/agent-exec-trace/issues).
Use the [bug report template](.github/ISSUE_TEMPLATE/) when available. We aim to
acknowledge all bug reports within a few days.

## Feature Requests

Open a [GitHub Issue](https://github.com/deghosal-2026/agent-exec-trace/issues)
with the `enhancement` label. We respond to enhancement requests as capacity allows.

## Development Setup

```bash
make setup       # install dependencies, pre-commit hooks
make stack-up    # start local services
make test        # run the full test suite
```

Requires Python 3.10+ and Docker.

## Quality Gates

Before opening a pull request, ensure:

- `ruff check` passes with zero warnings
- `mypy --strict` passes with zero errors
- `pytest` is green
- Test coverage is maintained

## Testing Policy

New features and major functionality changes must include tests added to the
automated test suite. Bug fixes should include a regression test.

## Pull Request Process

1. Fork the repository.
2. Create a feature branch.
3. Make your changes with tests.
4. Run quality gates locally (`make test`).
5. Open a pull request against `main`.

See [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md) for detailed contribution
guidelines, coding conventions, and the monorepo layout.

## Issue Tracking

We use GitHub Issues for tracking bugs and features. See the
[issue templates](.github/ISSUE_TEMPLATE/).

Labels: `bug`, `enhancement`, `adapter`, `docs`, `good first issue`.

## Code of Conduct

Everyone interacting in this project must follow the
[Code of Conduct](CODE_OF_CONDUCT.md). Security reports: see [SECURITY.md](SECURITY.md).