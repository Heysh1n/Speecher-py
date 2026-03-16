# 📂 Smart File Collector (fc.py)

A CLI/TUI utility for smartly collecting project source code into a single text file. 
Created specifically to seamlessly feed your codebase into AI chats (ChatGPT, Claude, Gemini) without the headache.

**Problem:** Manually copying dozens of files into an AI chat is pure agony. The project tree gets lost, junk files (like `node_modules` or `.env`) pollute the context, and character limits break long messages.
**Solution:** `fc.py`. Run it, select the necessary files (or pass a pattern), and the script will automatically build the tree, filter out the garbage, split the output if limits are exceeded, and push the result straight to your clipboard.

## 🚀 Features
- **Zero Dependencies:** Pure Python 3.7+ (stdlib only).
- **Cross-platform:** Works on Windows, macOS, and Linux.
- **Interactive TUI:** Convenient terminal dashboard with navigation and checkboxes.
- **Smart Ignore:** Built-in filters for `.git`, `node_modules`, `__pycache__`, `.venv`, `.env`, binaries, and media files.
- **Auto-Split:** Smart output slicing into `_p1.txt`, `_p2.txt` files if the AI chat character limit is exceeded.
- **Presets:** Save your favorite path configurations for frequent collections.

## 📦 Installation
Simply download the `fc.py` file and drop it into your project root (or add it to your `PATH`).
No `pip install` garbage required.

## ⚡ Quick Start

**Scenario 1: Interactive mode (TUI)**
```bash
python fc.py

```

*Opens a visual panel for checkbox file selection.*

**Scenario 2: Quickly collect everything (respecting ignore lists)**

```bash
python fc.py all -o context.txt

```

**Scenario 3: Collect specific files by pattern**

```bash
python fc.py pick "src/**/*.ts" "docker-compose.yml"

```

## 🎮 Interactive Panel (TUI)

Run `python fc.py` without arguments to open the main menu.

```text
=========================================
 📂 SMART FILE COLLECTOR
=========================================
 [1] Browse & Select (Manual file selection)
 [2] Search          (Find files via glob pattern)
 [3] Quick Pick      (Paste paths as a list)
 [4] Collect ALL     (Collect the entire project)
 [5] Presets         (Saved file configurations)
 [6] View tree       (Project tree with sizes)
 [7] Settings        (Output and limit configurations)
 ---------------------------------------
 [c] Collect selected | [v] Preview | [x] Clear | [q] Quit
=========================================

```

The **Browse & Select** mode supports:

* Toggle files by numbers: `1`, `3`, `5-8`
* Global selection: `select all`, `deselect`
* Search/Filter: `/`
* Select by pattern: `p`
* Page navigation: `<` and `>`

*After a successful collection (`c` key), the script will prompt you to copy the result directly to your clipboard.*

## 💻 CLI Commands

For automation and scripting.

| Command | Description | Example |
| --- | --- | --- |
| `all` | Collects all project files. | `python fc.py all` |
| `pick` | Collects files by specific path or glob pattern. | `python fc.py pick src/main.py "*.json"` |
| `pick -` | Interactive multi-line path input (great for copy-pasting). | `python fc.py pick -` |
| `tree` | Outputs the project structure. | `python fc.py tree` (add `-s` for sizes) |
| `find` | Finds files and suggests a `pick` command. | `python fc.py find "*.service.ts"` |
| `from` | Reads paths from a text file. | `python fc.py from paths.txt` |

**Common flags:**

* `-p`, `--path` : Target root directory (defaults to current).
* `-o`, `--output` : Output filename (defaults to console/clipboard).
* `-c`, `--chars` : Max characters per chunk (to bypass AI limits).
* `--no-tree` : Exclude the file tree from the final output.
* `-i`, `--ignore` : Additional folders to ignore (`-i "temp, logs"`).

## 💾 Presets

Tired of selecting the same backend files every time? Save them to a preset (written to a local `.fc-presets.json`).

```bash
# Save the current config set
python fc.py preset save config-files "src/config/*" ".env.example"

# Use a saved preset
python fc.py preset config-files

# List all presets
python fc.py preset list

# Delete a preset
python fc.py preset delete config-files

```

## ⚙️ Output Format

The final text is formatted exactly how neural networks "love" and understand best:

1. **Header:** Stats (file count, date).
2. **Tree:** ASCII structure of the provided files (so the AI grasps the architecture).
3. **Code:** Blocks containing full paths and content.

```text
==================================================
 Project File Collection
==================================================
Date: 2026-03-16
Files included: 2

--- Project Tree ---
src/
  ├── main.py
  └── utils/
      └── helper.py

==================================================
 File: src/main.py
==================================================
def main():
    print("Hello AI!")
...

```

## 💡 Tips & Tricks (For AI Workflows)

1. **Don't feed the AI everything.** Fixing a DB bug? Use `python fc.py pick "src/db/*" "src/models/*"`. Less garbage in the context = smarter AI response.
2. **Limits are your friends.** If the project is massive, go to TUI `Settings` and tweak `max chars per part`. The script will neatly slice the project into chunks you can feed into the chat one by one.
3. **Use `Quick Pick`.** AI told you to "modify these 5 files"? Copy its list, hit `3` in the TUI, and just paste the text.
