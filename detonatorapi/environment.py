"""Load project environment variables from the repository's `.env` file."""

from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_project_environment() -> None:
    """Load `.env` without replacing values supplied by the process environment."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)