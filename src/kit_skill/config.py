from __future__ import annotations

import os
from pathlib import Path


DEFAULT_BASE_URL = "https://api.kit.com/v4"
DEFAULT_TIMEOUT = 30


def _load_env_file(env_file: Path) -> bool:
    if not env_file.exists():
        return False
    with env_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"\'')
            if key and key not in os.environ:
                os.environ[key] = value
    return True


def load_dotenv(explicit_env_file: str | None = None) -> Path | None:
    candidates: list[Path] = []

    if explicit_env_file:
        candidates.append(Path(explicit_env_file).expanduser().resolve())

    env_from_var = os.getenv("KIT_ENV_FILE")
    if env_from_var:
        candidates.append(Path(env_from_var).expanduser().resolve())

    package_dir = Path(__file__).resolve().parent
    candidates.extend((parent / ".env") for parent in [package_dir] + list(package_dir.parents))

    cwd = Path.cwd()
    candidates.extend((parent / ".env") for parent in [cwd] + list(cwd.parents))

    seen: set[Path] = set()
    for env_file in candidates:
        if env_file in seen:
            continue
        seen.add(env_file)
        if _load_env_file(env_file):
            return env_file
    return None


def get_api_key() -> str:
    api_key = os.getenv("KIT_API_KEY")
    if not api_key:
        raise ValueError("KIT_API_KEY is required in environment or .env")
    if api_key.startswith("op://"):
        raise ValueError(
            "KIT_API_KEY appears to be an unresolved 1Password reference. "
            "Run through `op run --env-file=.env -- ...` or export a resolved key."
        )
    return api_key


def get_base_url() -> str:
    return os.getenv("KIT_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def get_timeout() -> int:
    return int(os.getenv("KIT_TIMEOUT", str(DEFAULT_TIMEOUT)))


def get_default_email_address() -> str | None:
    return os.getenv("KIT_DEFAULT_EMAIL_ADDRESS") or None


def get_default_template_id() -> int | None:
    raw_value = os.getenv("KIT_DEFAULT_EMAIL_TEMPLATE_ID")
    if not raw_value:
        return None
    return int(raw_value)
