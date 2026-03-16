# fc/panel.py
"""Interactive TUI panel for browsing, selecting and collecting files."""

import os
import sys
import fnmatch
from pathlib import Path

from fc.config import MAX_CHARS, PAGE_SIZE
from fc.colors import C
from fc.utils import term_width, fmt_size
from fc.core import get_all_files, resolve_patterns, read_safe
from fc.tree import build_tree
from fc.output import write_output
from fc.clipboard import copy_to_clipboard
from fc.presets import load_presets, save_presets


class Panel:
    def __init__(
        self,
        root: str = ".",
        output: str = "collected_output.txt",
        max_chars: int = MAX_CHARS,
        extra_ignore: set[str] | None = None,
    ):
        self.root = Path(root).resolve()
        self.output = output
        self.max_chars = max_chars
        self.show_tree = True
        self.auto_copy = False
        self.page_size = PAGE_SIZE
        self.extra_ignore = extra_ignore

        self.selected: set[str] = set()
        self.filter_text = ""
        self.page = 0
        self.all_files: list[Path] = []
        self.rel_paths: list[str] = []
        self.refresh()

    # ─── Helpers ──────────────────────────────

    def refresh(self) -> None:
        self.all_files = get_all_files(self.root, self.extra_ignore)
        self.rel_paths = [
            str(f.relative_to(self.root)).replace("\\", "/")
            for f in self.all_files
        ]
        self.selected = {s for s in self.selected if s in set(self.rel_paths)}

    def clear(self) -> None:
        os.system("cls" if os.name == "nt" else "clear")

    def prompt(self, text: str = "▸ ") -> str:
        try:
            return input(f" {C.CYAN}{text}{C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            return "q"

    def wait(self, msg: str = "Enter — continue...") -> None:
        try:
            input(f"\n {C.DIM}{msg}{C.RESET}")
        except (EOFError, KeyboardInterrupt):
            pass

    def display_indices(self) -> list[int]:
        if not self.filter_text:
            return list(range(len(self.all_files)))
        ft = self.filter_text.lower()
        return [i for i, r in enumerate(self.rel_paths) if ft in r.lower()]

    @staticmethod
    def parse_nums(s: str, mx: int) -> set[int]:
        result: set[int] = set()
        for part in s.replace(" ", "").split(","):
            if "-" in part and not part.startswith("-"):
                try:
                    a, b = part.split("-", 1)
                    result.update(range(int(a), int(b) + 1))
                except ValueError:
                    pass
            else:
                try:
                    result.add(int(part))
                except ValueError:
                    pass
        return {n for n in result if 1 <= n <= mx}

    def _offer_clipboard(self, created: list[tuple[Path, int]]) -> None:
        if not created:
            return
        if self.auto_copy:
            self._do_copy(created)
            return
        inp = self.prompt("Copy to clipboard? (y/n): ")
        if inp.lower() in ("y", "yes", "д", "да"):
            self._do_copy(created)

    def _do_copy(self, created: list[tuple[Path, int]]) -> None:
        try:
            text = "".join(Path(fn).read_text("utf-8") for fn, _ in created)
            if copy_to_clipboard(text):
                print(f"  {C.GREEN}📋 Copied to clipboard!{C.RESET}")
            else:
                print(f"  {C.YELLOW}⚠️  Clipboard unavailable{C.RESET}")
        except Exception as e:
            print(f"  {C.RED}⚠️  {e}{C.RESET}")

    # ─── Header ───────────────────────────────

    def header(self, subtitle: str = "") -> str:
        sel = (
            f"  {C.GREEN}✓ {len(self.selected)} selected{C.RESET}"
            if self.selected
            else ""
        )
        h = f"\n {C.BOLD}{C.CYAN}━━━ {C.RESET}{C.BOLD}🔧 Smart File Collector{C.RESET}{C.BOLD}{C.CYAN} ━━━━━━━━━━━━━{C.RESET}\n"
        h += f" 📂 {self.root.name}  │  📄 {len(self.all_files)} files{sel}\n"
        if subtitle:
            h += f" {C.DIM}{subtitle}{C.RESET}\n"
        h += f" {C.CYAN}{'━' * 44}{C.RESET}"
        return h

    # ─── Main Menu ────────────────────────────

    def run(self) -> None:
        if not self.root.is_dir():
            print(f"{C.RED}❌ Not a directory: {self.root}{C.RESET}")
            return
        try:
            while True:
                self.main_menu()
        except (EOFError, KeyboardInterrupt):
            print(f"\n {C.DIM}👋 Bye{C.RESET}")

    def main_menu(self) -> None:
        self.clear()
        sel = len(self.selected)
        print(self.header())
        print(f"""
  {C.BOLD}1{C.RESET} │ 📂  Browse & Select
  {C.BOLD}2{C.RESET} │ 🔍  Search by pattern
  {C.BOLD}3{C.RESET} │ 📝  Quick pick (paste paths)
  {C.BOLD}4{C.RESET} │ 📋  Collect ALL files
  {C.BOLD}5{C.RESET} │ 🔖  Presets
  {C.BOLD}6{C.RESET} │ 🗂️   View tree
  {C.BOLD}7{C.RESET} │ ⚙️   Settings
  {'─' * 3}┤{'─' * 28}
  {C.BOLD}c{C.RESET} │ ✅  Collect selected ({sel})
  {C.BOLD}v{C.RESET} │ 👁️   Preview selected
  {C.BOLD}x{C.RESET} │ 🗑️   Clear selection
  {'─' * 3}┤{'─' * 28}
  {C.BOLD}0{C.RESET} │ ❌  Exit""")

        ch = self.prompt()
        actions = {
            "1": self.browse,
            "2": self.search,
            "3": self.quick_pick,
            "4": self.collect_all,
            "5": self.presets_menu,
            "6": self.tree_view,
            "7": self.settings_menu,
            "c": self.do_collect,
            "v": self.preview,
            "x": self.clear_sel,
        }
        if ch in ("0", "q", "exit", "quit"):
            print(f"\n {C.DIM}👋 Bye{C.RESET}")
            sys.exit(0)
        if ch in actions:
            actions[ch]()

    # ─── Browse ───────────────────────────────

    def browse(self) -> None:
        self.page = 0
        self.filter_text = ""

        while True:
            self.clear()
            di = self.display_indices()
            total = len(di)

            if total == 0:
                print(f"\n  {C.YELLOW}⚠️  No files match: '{self.filter_text}'{C.RESET}")
                self.filter_text = ""
                self.wait()
                continue

            pages = (total + self.page_size - 1) // self.page_size
            self.page = max(0, min(self.page, pages - 1))
            start = self.page * self.page_size
            end = min(start + self.page_size, total)
            page_items = di[start:end]

            finfo = f"  │  filter: '{self.filter_text}'" if self.filter_text else ""
            print(
                f"\n {C.BOLD}📂 Browse{C.RESET}  page {self.page + 1}/{pages}"
                f" ({start + 1}–{end} / {total}){finfo}"
            )
            if self.selected:
                print(f" {C.GREEN}✓ {len(self.selected)} selected{C.RESET}")
            print(f" {'─' * 56}")

            pw = max(30, term_width() - 24)
            for j, gi in enumerate(page_items):
                num = start + j + 1
                rel = self.rel_paths[gi]
                check = f"{C.GREEN}✓{C.RESET}" if rel in self.selected else " "
                fp = self.all_files[gi]
                sz = fmt_size(fp.stat().st_size) if fp.exists() else "?"
                dp = rel if len(rel) <= pw else "…" + rel[-(pw - 1) :]
                print(
                    f"  [{check}] {C.DIM}{num:>4}{C.RESET}  {dp:<{pw}}  {C.DIM}{sz:>6}{C.RESET}"
                )

            print(f"\n {'─' * 56}")
            print(
                f"  Toggle: {C.BOLD}1,3,5-8{C.RESET}   {C.BOLD}a{C.RESET}:all"
                f"  {C.BOLD}n{C.RESET}:none  {C.BOLD}/{C.RESET}:filter  {C.BOLD}p{C.RESET}:pattern"
            )
            extra = f"  {C.BOLD}c{C.RESET}:clear filter" if self.filter_text else ""
            print(f"  {C.BOLD}<{C.RESET}:prev  {C.BOLD}>{C.RESET}:next  {C.BOLD}d{C.RESET}:done{extra}")

            inp = self.prompt()

            if not inp or inp in ("d", "q"):
                self.filter_text = ""
                return
            elif inp == "<":
                self.page = max(0, self.page - 1)
            elif inp == ">":
                self.page = min(pages - 1, self.page + 1)
            elif inp == "a":
                for idx in di:
                    self.selected.add(self.rel_paths[idx])
            elif inp == "n":
                if self.filter_text:
                    for idx in di:
                        self.selected.discard(self.rel_paths[idx])
                else:
                    self.selected.clear()
            elif inp == "c":
                self.filter_text = ""
                self.page = 0
            elif inp == "/":
                ft = self.prompt("Filter: ")
                if ft:
                    self.filter_text = ft
                    self.page = 0
            elif inp == "p":
                pat = self.prompt("Glob: ")
                if pat:
                    cnt = 0
                    for idx in di:
                        rel = self.rel_paths[idx]
                        if (
                            fnmatch.fnmatch(rel, pat)
                            or fnmatch.fnmatch(Path(rel).name, pat)
                            or fnmatch.fnmatch(rel, "*/" + pat)
                        ):
                            self.selected.add(rel)
                            cnt += 1
                    print(f"  {C.GREEN}+{cnt} selected{C.RESET}")
                    self.wait()
            else:
                nums = self.parse_nums(inp, total)
                for num in nums:
                    gi = di[num - 1]
                    rel = self.rel_paths[gi]
                    if rel in self.selected:
                        self.selected.discard(rel)
                    else:
                        self.selected.add(rel)

    # ─── Search ───────────────────────────────

    def search(self) -> None:
        self.clear()
        print(f"\n {C.BOLD}🔍 Search{C.RESET}\n {'─' * 40}")
        print(f" Glob: *.service.ts, **/APIs/*, etc.\n")

        pat = self.prompt("Pattern: ")
        if not pat:
            return

        matched = [
            i
            for i, rel in enumerate(self.rel_paths)
            if fnmatch.fnmatch(rel, pat)
            or fnmatch.fnmatch(Path(rel).name, pat)
            or fnmatch.fnmatch(rel, "*/" + pat)
        ]

        if not matched:
            print(f"\n  {C.RED}❌ Nothing matches: {pat}{C.RESET}")
            self.wait()
            return

        self.clear()
        print(f"\n {C.BOLD}🔍 Results for '{pat}' — {len(matched)} files{C.RESET}\n {'─' * 40}\n")

        for idx in matched:
            rel = self.rel_paths[idx]
            check = f"{C.GREEN}✓{C.RESET}" if rel in self.selected else " "
            print(f"  [{check}]  {rel}")

        print(f"\n  {C.BOLD}a{C.RESET}:select all  {C.BOLD}n{C.RESET}:deselect all  {C.BOLD}Enter{C.RESET}:back")
        inp = self.prompt()
        if inp == "a":
            for idx in matched:
                self.selected.add(self.rel_paths[idx])
            print(f"  {C.GREEN}✓ +{len(matched)}{C.RESET}")
            self.wait()
        elif inp == "n":
            for idx in matched:
                self.selected.discard(self.rel_paths[idx])

    # ─── Quick Pick ───────────────────────────

    def quick_pick(self) -> None:
        self.clear()
        print(f"\n {C.BOLD}📝 Quick Pick{C.RESET}\n {'─' * 40}")
        print(f" Paste paths / patterns, one per line. Empty = done\n")

        patterns: list[str] = []
        while True:
            line = self.prompt("  ")
            if not line:
                break
            for part in line.split():
                patterns.append(part)

        if not patterns:
            return

        picked = resolve_patterns(self.root, patterns, self.all_files)
        if not picked:
            print(f"\n  {C.RED}❌ No files matched{C.RESET}")
            self.wait()
            return

        for fp in picked:
            self.selected.add(str(fp.relative_to(self.root)).replace("\\", "/"))

        print(f"\n  {C.GREEN}✓ {len(picked)} files added to selection{C.RESET}")
        self.wait()

    # ─── Collect ──────────────────────────────

    def collect_all(self) -> None:
        self.clear()
        print(f"\n  Collecting all {len(self.all_files)} files...")
        created = write_output(
            self.root, self.all_files, self.output, "all", self.show_tree, self.max_chars
        )
        self._offer_clipboard(created)
        self.wait()

    def do_collect(self) -> None:
        if not self.selected:
            print(f"\n  {C.YELLOW}⚠️  Nothing selected{C.RESET}")
            self.wait()
            return

        files = [
            self.root / r
            for r in sorted(self.selected)
            if (self.root / r).exists()
        ]
        if not files:
            print(f"\n  {C.RED}❌ No valid files{C.RESET}")
            self.wait()
            return

        self.clear()
        print(f"\n  Collecting {len(files)} files...")
        created = write_output(
            self.root, files, self.output, "pick", self.show_tree, self.max_chars
        )
        self._offer_clipboard(created)
        self.wait()

    # ─── Preview ──────────────────────────────

    def preview(self) -> None:
        self.clear()
        if not self.selected:
            print(f"\n  {C.YELLOW}⚠️  Nothing selected{C.RESET}")
            self.wait()
            return

        print(f"\n {C.BOLD}👁️  Selected ({len(self.selected)}){C.RESET}\n {'─' * 40}\n")

        total_sz = 0
        for rel in sorted(self.selected):
            fp = self.root / rel
            if fp.exists():
                sz = fp.stat().st_size
                total_sz += sz
                print(f"  {C.GREEN}✓{C.RESET} {rel}  {C.DIM}({fmt_size(sz)}){C.RESET}")
            else:
                print(f"  {C.RED}✗ {rel} (missing){C.RESET}")

        est = sum(
            len(read_safe(self.root / r)) + 100
            for r in self.selected
            if (self.root / r).exists()
        )
        parts_est = max(1, est // self.max_chars + (1 if est % self.max_chars else 0))
        print(f"\n  Total: {fmt_size(total_sz)} | ~{est:,} chars | ~{parts_est} part(s)")
        self.wait()

    def clear_sel(self) -> None:
        n = len(self.selected)
        self.selected.clear()
        print(f"\n  {C.GREEN}✓ Cleared {n} items{C.RESET}")
        self.wait()

    # ─── Tree ─────────────────────────────────

    def tree_view(self) -> None:
        self.clear()
        print(f"\n{build_tree(self.root, self.all_files, sizes=True)}")
        print(f"\n 📄 Total: {len(self.all_files)} files")
        self.wait()

    # ─── Settings ─────────────────────────────

    def settings_menu(self) -> None:
        while True:
            self.clear()
            tree_s = f"{C.GREEN}ON{C.RESET}" if self.show_tree else f"{C.RED}OFF{C.RESET}"
            copy_s = f"{C.GREEN}ON{C.RESET}" if self.auto_copy else f"{C.RED}OFF{C.RESET}"

            print(f"\n {C.BOLD}⚙️  Settings{C.RESET}\n {'─' * 40}")
            print(f"""
  {C.BOLD}1{C.RESET} │ Output file:     {self.output}
  {C.BOLD}2{C.RESET} │ Max chars/part:   {self.max_chars:,}
  {C.BOLD}3{C.RESET} │ Include tree:     {tree_s}
  {C.BOLD}4{C.RESET} │ Auto clipboard:   {copy_s}
  {C.BOLD}5{C.RESET} │ Page size:        {self.page_size}
  {C.BOLD}6{C.RESET} │ Refresh files     ({len(self.all_files)} indexed)
  {'─' * 3}┤{'─' * 28}
  {C.BOLD}0{C.RESET} │ Back""")

            inp = self.prompt()
            if inp in ("0", "q", ""):
                return
            elif inp == "1":
                v = self.prompt("Output file: ")
                if v:
                    self.output = v
            elif inp == "2":
                v = self.prompt("Max chars: ")
                try:
                    self.max_chars = max(5000, int(v))
                except ValueError:
                    pass
            elif inp == "3":
                self.show_tree = not self.show_tree
            elif inp == "4":
                self.auto_copy = not self.auto_copy
            elif inp == "5":
                v = self.prompt("Page size: ")
                try:
                    self.page_size = max(5, min(100, int(v)))
                except ValueError:
                    pass
            elif inp == "6":
                self.refresh()
                print(f"  {C.GREEN}✓ {len(self.all_files)} files indexed{C.RESET}")
                self.wait()

    # ─── Presets ──────────────────────────────

    def presets_menu(self) -> None:
        while True:
            self.clear()
            presets = load_presets(self.root)

            print(f"\n {C.BOLD}🔖 Presets{C.RESET}\n {'─' * 40}\n")

            names = sorted(presets.keys())
            if names:
                for i, name in enumerate(names, 1):
                    pats = presets[name]
                    print(f"  {C.BOLD}{i}{C.RESET} │ {name}  {C.DIM}({len(pats)} patterns){C.RESET}")
            else:
                print(f"  {C.DIM}No presets yet{C.RESET}")

            print(f"""
  {'─' * 3}┤{'─' * 28}
  {C.BOLD}s{C.RESET} │ Save selection as preset
  {C.BOLD}u{C.RESET} │ Use preset (add to selection)
  {C.BOLD}d{C.RESET} │ Delete preset
  {C.BOLD}e{C.RESET} │ Export preset → collect
  {'─' * 3}┤{'─' * 28}
  {C.BOLD}0{C.RESET} │ Back""")

            inp = self.prompt()
            if inp in ("0", "q", ""):
                return
            elif inp == "s":
                if not self.selected:
                    print(f"  {C.YELLOW}⚠️  Nothing selected{C.RESET}")
                    self.wait()
                    continue
                name = self.prompt("Name: ")
                if name:
                    presets[name] = sorted(self.selected)
                    save_presets(presets, self.root)
                    print(f"  {C.GREEN}✓ Saved '{name}' ({len(self.selected)} files){C.RESET}")
                    self.wait()
            elif inp == "u":
                if not names:
                    continue
                num = self.prompt("Number: ")
                try:
                    name = names[int(num) - 1]
                    picked = resolve_patterns(self.root, presets[name], self.all_files)
                    for fp in picked:
                        self.selected.add(
                            str(fp.relative_to(self.root)).replace("\\", "/")
                        )
                    print(f"  {C.GREEN}✓ +{len(picked)} files from '{name}'{C.RESET}")
                    self.wait()
                except (ValueError, IndexError):
                    print(f"  {C.RED}Invalid{C.RESET}")
                    self.wait()
            elif inp == "d":
                if not names:
                    continue
                num = self.prompt("Delete number: ")
                try:
                    name = names[int(num) - 1]
                    del presets[name]
                    save_presets(presets, self.root)
                    print(f"  {C.GREEN}✓ Deleted '{name}'{C.RESET}")
                    self.wait()
                except (ValueError, IndexError):
                    print(f"  {C.RED}Invalid{C.RESET}")
                    self.wait()
            elif inp == "e":
                if not names:
                    continue
                num = self.prompt("Number: ")
                try:
                    name = names[int(num) - 1]
                    picked = resolve_patterns(self.root, presets[name], self.all_files)
                    if picked:
                        print(f"\n  Collecting preset '{name}' ({len(picked)} files)...")
                        created = write_output(
                            self.root, picked, self.output,
                            f"preset:{name}", self.show_tree, self.max_chars,
                        )
                        self._offer_clipboard(created)
                    self.wait()
                except (ValueError, IndexError):
                    print(f"  {C.RED}Invalid{C.RESET}")
                    self.wait()