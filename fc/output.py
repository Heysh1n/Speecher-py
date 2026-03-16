
# fc/output.py
"""Output file writer with auto-splitting."""

from pathlib import Path
from datetime import datetime

from fc.core import read_safe
from fc.tree import build_tree
from fc.config import MAX_CHARS
from fc.colors import C


def write_output(
    root: Path,
    files: list[Path],
    output: str,
    mode: str = "panel",
    show_tree: bool = True,
    max_chars: int = MAX_CHARS,
) -> list[tuple[Path, int]]:
    """Write collected files to output. Returns list of (path, char_count)."""
    if not files:
        print("⚠️  No files")
        return []

    root = Path(root) if not isinstance(root, Path) else root
    total = len(files)
    now = datetime.now()

    # ── File blocks ──
    blocks: list[str] = []
    for i, fp in enumerate(files, 1):
        rel = str(fp.relative_to(root)).replace("\\", "/")
        content = read_safe(fp)
        if not content.endswith("\n"):
            content += "\n"
        blocks.append(
            f"┌─── 📄 [{i}/{total}] {rel}\n{content}└{'─' * 40}\n\n"
        )

    # ── Tree section ──
    tree_sec = ""
    if show_tree:
        tbody = build_tree(root, files)
        tree_sec = f"┌{'─' * 12}\n│ 🗂️  STRUCTURE\n├{'─' * 12}\n"
        for line in tbody.split("\n"):
            tree_sec += f"│ {line}\n"
        tree_sec += f"└{'─' * 12}\n\n"

    # ── Builders ──
    def mk_h(p: int | None = None, tp: int | None = None) -> str:
        tag = f" ({p}/{tp})" if p and tp and tp > 1 else ""
        return (
            f"{'═' * 14}\n📋 {root.name} [{mode}]{tag}\n"
            f"📅 {now:%d.%m.%Y %H:%M:%S}\n📄 Files: {total}\n{'═' * 14}\n\n"
        )

    def mk_c(p: int, tp: int) -> str:
        return f"{'═' * 5}\n📋 {root.name} ({p}/{tp})\n↳ continued\n{'═' * 5}\n\n"

    def mk_f(p: int, tp: int, last: bool) -> str:
        if last:
            return f"{'═' * 5}\n✅ End\n{'═' * 5}\n"
        return f"{'═' * 5}\n➡️ Part {p + 1}/{tp}\n{'═' * 5}\n"

    # ── Split ──
    initial = mk_h() + tree_sec
    parts: list[str] = []
    current = initial
    first = True

    for block in blocks:
        if len(current) + len(block) > max_chars and current != initial:
            parts.append(current)
            current = ""
            first = False
        if not current:
            current = initial if first else ""
        current += block

    if current:
        parts.append(current)

    # ── Fix headers ──
    tp = len(parts)
    final: list[str] = []
    for i, part in enumerate(parts):
        if i == 0 and tp > 1:
            part = part.replace(mk_h(), mk_h(1, tp), 1)
        elif i > 0:
            part = mk_c(i + 1, tp) + part
        part += mk_f(i + 1, tp, i == tp - 1)
        final.append(part)

    # ── Write ──
    op = Path(output)
    stem, sfx = op.stem, op.suffix or ".txt"
    created: list[tuple[Path, int]] = []

    for i, content in enumerate(final):
        fn = op if tp == 1 else op.parent / f"{stem}_p{i + 1}{sfx}"
        fn.parent.mkdir(parents=True, exist_ok=True)
        fn.write_text(content, encoding="utf-8")
        created.append((fn, len(content)))

    print(f"\n  {C.GREEN}✅ {len(created)} file(s):{C.RESET}")
    for fn, ch in created:
        print(f"     📄 {fn.name}: {ch:,} chars")

    return created