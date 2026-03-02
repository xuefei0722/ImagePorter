# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: primary Flet desktop application entry point and Docker image workflow logic.
- `test.py`: alternate UI/prototyping entry point; use only for experimentation, not as an automated test suite.
- `assets/`: static assets (for example `assets/icon.png` used in packaging).
- `docs/BUILD_GUIDE.md`: native build notes (currently macOS-focused).
- `requirements.txt`: runtime Python dependencies.
- `build/`, `dist/`, `*.app`, `*.exe`: generated artifacts; do not commit.

## Build, Test, and Development Commands
- `python3 -m venv .venv && source .venv/bin/activate`: create and activate local virtual environment.
- `pip install -r requirements.txt`: install dependencies (`flet`, docker CLI integration helpers).
- `flet run main.py` or `python main.py`: run the main app locally.
- `python test.py`: run the alternate UI sandbox for manual comparison checks.
- `flet build macos --icon assets/icon.png`: build a macOS app bundle (see `docs/BUILD_GUIDE.md`).

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation and clear, small helper functions.
- Use `snake_case` for functions/variables, `PascalCase` for classes (for example `TaskRow`).
- Keep UI update logic explicit and thread-safe; avoid hidden side effects in callbacks.
- Prefer module-level constants for reused literals/paths.

## Testing Guidelines
- There is no formal `pytest`/`unittest` suite yet.
- Validate changes with manual smoke tests:
  - launch app (`flet run main.py`),
  - verify image parsing/validation,
  - run one successful and one failing Docker pull/save flow,
  - confirm logs/progress rendering and output path behavior.
- If adding non-trivial logic, include focused tests in a new `tests/` directory and document how to run them.

## Commit & Pull Request Guidelines
- Follow existing commit style: Conventional Commit prefix + concise summary, e.g. `feat: ...`, `refactor: ...`, `fix: ...`.
- Keep commits scoped to a single concern.
- PRs should include:
  - purpose and behavior change summary,
  - linked issue (if any),
  - local verification steps,
  - screenshots/GIFs for UI updates.

## Security & Configuration Tips
- Docker must be installed and accessible in `PATH`.
- Never commit local environment files or secrets (`.env*`, local logs, build outputs).
