# fc/clipboard.py
"""Cross-platform clipboard support."""

import sys
import subprocess


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True on success."""
    try:
        if sys.platform == "darwin":
            subprocess.run(
                ["pbcopy"], input=text.encode("utf-8"), check=True
            )
        elif sys.platform == "win32":
            subprocess.run(
                ["clip"], input=text.encode("utf-16-le"), check=True
            )
        else:
            # Linux — try xclip, fallback to xsel
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode("utf-8"),
                    check=True,
                )
            except FileNotFoundError:
                subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=text.encode("utf-8"),
                    check=True,
                )
        return True
    except Exception:
        return False