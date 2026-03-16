
# fc/colors.py
"""Terminal color helpers with auto-detection."""

import sys


class C:
    """ANSI color codes. Auto-disabled when stdout is not a TTY."""

    _on: bool = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    RESET   = "\033[0m"  if _on else ""
    BOLD    = "\033[1m"  if _on else ""
    DIM     = "\033[2m"  if _on else ""
    RED     = "\033[31m" if _on else ""
    GREEN   = "\033[32m" if _on else ""
    YELLOW  = "\033[33m" if _on else ""
    BLUE    = "\033[34m" if _on else ""
    MAGENTA = "\033[35m" if _on else ""
    CYAN    = "\033[36m" if _on else ""