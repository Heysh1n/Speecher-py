# fc/config.py
"""Global settings and ignore lists."""

from pathlib import Path

VERSION = "2.0.0"
APP_NAME = "fc"
APP_TITLE = "🔧 Smart File Collector"

MAX_CHARS = 90_000
PAGE_SIZE = 20

PRESETS_FILENAME = ".fc-presets.json"

IGNORE_DIRS: set[str] = {
    "__pycache__", ".git", ".svn", "node_modules", ".venv", "venv", "env",
    ".idea", ".vscode", "dist", "build", "__MACOSX", ".mypy_cache",
    ".pytest_cache",
}

IGNORE_FILES: set[str] = {
    ".DS_Store", "Thumbs.db", ".gitignore", "package-lock.json",
    "poetry.lock", ".env"
}

IGNORE_EXTENSIONS: set[str] = {
    ".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg",
    ".mp3", ".mp4", ".avi", ".mov", ".zip", ".tar", ".gz",
    ".rar", ".7z", ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".db", ".sqlite", ".sqlite3",
}


def get_self_files() -> set[str]:
    """Files that belong to fc itself — always skip."""
    return {"fc.py", "__main__.py"}


def get_presets_path(root: Path | None = None) -> Path:
    """Presets file location — next to the working directory."""
    base = root or Path.cwd()
    return base / PRESETS_FILENAME