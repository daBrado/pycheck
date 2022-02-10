# pycheck

A simple conglomeration of various tools to check Python code:

- black
- flake8
- flake8-bugbear
- isort
- mypy
- pytest

It is designed to be added via `poetry add -D` and run via
`poetry run pycheck [--watch]`, with configuration handled by `pyproject.toml` and
`.flake8`.
