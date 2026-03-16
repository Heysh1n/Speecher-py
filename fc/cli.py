
# fc/cli.py
"""CLI argument parser and command handlers."""

import sys
import fnmatch
import argparse
from pathlib import Path

from fc.config import MAX_CHARS, VERSION
from fc.core import get_all_files, resolve_patterns
from fc.tree import build_tree
from fc.output import write_output
from fc.presets import load_presets, save_presets
from fc.utils import fmt_size
from fc.panel import Panel


# ─── CLI Commands ─────────────────────────

def cmd_all(args: argparse.Namespace) -> None:
    root = Path(args.path).resolve()
    if not root.is_dir():
        return print(f"❌ Not a directory: {root}")
    extra = set(args.ignore) if args.ignore else None
    files = get_all_files(root, extra)
    print(f"📄 {len(files)} files")
    write_output(root, files, args.output, "all", not args.no_tree, args.chars)


def cmd_pick(args: argparse.Namespace) -> None:
    root = Path(args.path).resolve()
    if not root.is_dir():
        return print(f"❌ Not a directory: {root}")

    patterns = getattr(args, "files", None) or []

    if not patterns or patterns == ["-"]:
        print("📝 Paths (one per line, empty = done):")
        patterns = []
        while True:
            try:
                line = input("  > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                break
            patterns.append(line)

    if not patterns:
        return print("❌ No files")

    all_f = get_all_files(root)
    picked = resolve_patterns(root, patterns, all_f)
    if not picked:
        return print("❌ No matches")
    print(f"📄 {len(picked)} files")
    write_output(root, picked, args.output, "pick", not args.no_tree, args.chars)


def cmd_tree(args: argparse.Namespace) -> None:
    root = Path(args.path).resolve()
    if not root.is_dir():
        return print(f"❌ Not a directory: {root}")
    extra = set(args.ignore) if args.ignore else None
    files = get_all_files(root, extra)
    sizes = getattr(args, "sizes", False)
    print(f"\n{build_tree(root, files, sizes)}")
    print(f"\n📄 Total: {len(files)}")


def cmd_find(args: argparse.Namespace) -> None:
    root = Path(args.path).resolve()
    if not root.is_dir():
        return print(f"❌ Not a directory: {root}")

    pat = args.pattern
    all_f = get_all_files(root)
    matched = [
        f
        for f in all_f
        if fnmatch.fnmatch(f.name, pat)
        or fnmatch.fnmatch(str(f.relative_to(root)).replace("\\", "/"), pat)
    ]

    if not matched:
        return print(f"❌ Nothing matching: {pat}")

    print(f"\n🔍 {len(matched)} files:\n")
    parts = []
    for f in matched:
        rel = str(f.relative_to(root)).replace("\\", "/")
        print(f"  {rel}  ({fmt_size(f.stat().st_size)})")
        parts.append(f'"{rel}"')
    print(f'\n💡 fc pick {" ".join(parts)}')


def cmd_from(args: argparse.Namespace) -> None:
    lf = Path(args.list_file)
    if not lf.exists():
        return print(f"❌ Not found: {lf}")
    patterns = [
        line.strip()
        for line in lf.read_text("utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not patterns:
        return print("❌ Empty list")
    args.files = patterns
    cmd_pick(args)


def cmd_preset(args: argparse.Namespace) -> None:
    root = Path(args.path).resolve()
    presets = load_presets(root)
    pa = getattr(args, "preset_args", []) or []

    if not pa:
        print("Usage: preset list | save <name> files... | delete <name> | <name>")
        return

    action = pa[0]

    if action == "list":
        if not presets:
            return print("📋 No presets")
        for name, pats in sorted(presets.items()):
            print(f"  🔖 {name}: {', '.join(pats)}")

    elif action == "save":
        if len(pa) < 3:
            return print("Usage: preset save <name> file1 file2 ...")
        presets[pa[1]] = pa[2:]
        save_presets(presets, root)
        print(f"✅ Saved '{pa[1]}'")

    elif action == "delete":
        if len(pa) < 2:
            return print("Usage: preset delete <name>")
        if pa[1] in presets:
            del presets[pa[1]]
            save_presets(presets, root)
            print("✅ Deleted")
        else:
            print("❌ Not found")

    else:
        name = action
        if name not in presets:
            return print(f"❌ Preset '{name}' not found")
        args.files = presets[name]
        cmd_pick(args)


# ─── Parser ───────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-p", "--path", default=".", help="Root directory")
    common.add_argument("-o", "--output", default="collected_output.txt")
    common.add_argument("-c", "--chars", type=int, default=MAX_CHARS)
    common.add_argument("--no-tree", action="store_true")
    common.add_argument("-i", "--ignore", nargs="*", default=[])

    parser = argparse.ArgumentParser(
        prog="fc",
        description=f"🔧 Smart File Collector v{VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
  fc                                       Interactive panel
  fc all                                   Collect all files
  fc pick src/index.ts "src/config/*"      Pick specific files
  fc tree -s                               Tree with sizes
  fc find "*.service.ts"                   Search files
  fc preset save myp "path1" "path2"       Save preset
  fc preset myp                            Use preset
""",
    )
    parser.add_argument("-V", "--version", action="version", version=f"fc {VERSION}")

    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("all", parents=[common], help="Collect all files")

    sp = sub.add_parser("pick", parents=[common], help="Pick specific files")
    sp.add_argument("files", nargs="*")

    st = sub.add_parser("tree", parents=[common], help="Show file tree")
    st.add_argument("-s", "--sizes", action="store_true")

    sf = sub.add_parser("find", parents=[common], help="Find by pattern")
    sf.add_argument("pattern")

    sfr = sub.add_parser("from", parents=[common], help="Pick from list file")
    sfr.add_argument("list_file")

    spr = sub.add_parser("preset", parents=[common], help="Manage presets")
    spr.add_argument("preset_args", nargs="*")

    return parser


def main() -> None:
    # No args → interactive panel
    if len(sys.argv) < 2:
        Panel().run()
        return

    parser = build_parser()
    args = parser.parse_args()

    if not args.cmd:
        Panel(args.path, args.output, args.chars, set(args.ignore) if args.ignore else None).run()
        return

    handlers = {
        "all": cmd_all,
        "pick": cmd_pick,
        "tree": cmd_tree,
        "find": cmd_find,
        "from": cmd_from,
        "preset": cmd_preset,
    }
    handlers[args.cmd](args)