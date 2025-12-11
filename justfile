[private]
default:
  @just --list

# Format and lint code
[group('development')]
lint:
    uv run ruff check --fix .
    uv run ruff format .
