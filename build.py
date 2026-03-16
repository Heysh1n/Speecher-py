import os
import sys
import stat
import shutil
import platform
import subprocess
import site
from pathlib import Path
from textwrap import dedent

DIST_DIR = Path("dist")
BUILD_DIR = Path("build_temp")
APP_NAME = "fc"
PKG_DIR = Path("fc")
ENTRY_FILE = "fc/__main__.py"


# ════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════

def clean() -> None:
    for d in (DIST_DIR, BUILD_DIR):
        if d.is_dir():
            shutil.rmtree(d)
    for p in Path(".").glob("*.spec"):
        p.unlink()
    print("🧹 Cleaned")


def ensure_dist() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)


def platform_tag() -> str:
    s = platform.system().lower()
    a = platform.machine().lower()
    if s == "windows":
        return f"win-{a}"
    elif s == "darwin":
        return f"macos-{a}"
    return f"linux-{a}"


def make_executable(path: Path) -> None:
    if platform.system() != "Windows":
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def has_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def python_has_shared_lib() -> bool:
    try:
        import sysconfig
        cfg = sysconfig.get_config_vars()
        if cfg.get("Py_ENABLE_SHARED", 0):
            return True
        if cfg.get("INSTSONAME", ""):
            return True
        lib = cfg.get("LDLIBRARY", "")
        if lib and (".so" in lib or ".dylib" in lib):
            return True
        return False
    except Exception:
        return False


# ════════════════════════════════════════════
# BACKEND 1: ZIPAPP
# ════════════════════════════════════════════

def build_zipapp() -> Path:
    print(f"\n📦 Building with zipapp...")
    ensure_dist()

    tag = platform_tag()
    staging = BUILD_DIR / "zipapp_staging"

    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    shutil.copytree(PKG_DIR, staging / "fc", dirs_exist_ok=True)

    for cache in (staging / "fc").rglob("__pycache__"):
        shutil.rmtree(cache)

    (staging / "__main__.py").write_text(
        "from fc.cli import main\nmain()\n", encoding="utf-8"
    )

    pyz_path = DIST_DIR / f"{APP_NAME}-{tag}.pyz"

    import zipapp
    zipapp.create_archive(
        source=staging,
        target=pyz_path,
        interpreter="/usr/bin/env python3",
        compressed=True,
    )

    make_executable(pyz_path)

    if platform.system() == "Windows":
        wrapper = DIST_DIR / f"{APP_NAME}.bat"
        wrapper.write_text(
            f'@echo off\r\npython "%~dp0{pyz_path.name}" %*\r\n',
            encoding="utf-8",
        )
    else:
        wrapper = DIST_DIR / APP_NAME
        wrapper.write_text(
            f'#!/bin/sh\nexec python3 "$(dirname "$0")/{pyz_path.name}" "$@"\n',
            encoding="utf-8",
        )
        make_executable(wrapper)

    size_mb = pyz_path.stat().st_size / 1_048_576
    print(f"✅ Built: {pyz_path}  ({size_mb:.2f} MB)")
    print(f"   Wrapper: {wrapper}")
    return pyz_path


# ════════════════════════════════════════════
# BACKEND 2: NUITKA
# ════════════════════════════════════════════

def build_nuitka() -> Path:
    print(f"\n🔨 Building with Nuitka...")
    ensure_dist()

    # Auto-install patchelf on Linux
    if platform.system() == "Linux" and not has_command("patchelf"):
        print("  📦 Installing patchelf via pip...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "patchelf"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pip_bin = Path(sys.executable).parent
        os.environ["PATH"] = str(pip_bin) + os.pathsep + os.environ.get("PATH", "")

        if not has_command("patchelf"):
            for d in site.getsitepackages() + [site.getusersitepackages()]:
                candidate = Path(d).parent / "bin" / "patchelf"
                if candidate.exists():
                    os.environ["PATH"] = str(candidate.parent) + os.pathsep + os.environ["PATH"]
                    break

    tag = platform_tag()
    out_name = f"{APP_NAME}-{tag}"

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--output-dir=" + str(BUILD_DIR),
        f"--output-filename={out_name}",
        "--remove-output",
        "--assume-yes-for-downloads",
        "--include-package=fc",
        ENTRY_FILE,
    ]

    if platform.system() == "Linux":
        cmd.append("--static-libpython=auto")

    print(f"   Command: {' '.join(cmd)}\n")
    subprocess.check_call(cmd)

    suffix = ".exe" if platform.system() == "Windows" else ""
    exe = BUILD_DIR / f"{out_name}{suffix}"

    if not exe.exists():
        for candidate in BUILD_DIR.rglob(f"{out_name}{suffix}"):
            exe = candidate
            break

    if not exe.exists():
        raise FileNotFoundError(f"Nuitka output not found")

    final = DIST_DIR / exe.name
    shutil.move(str(exe), str(final))
    make_executable(final)

    size_mb = final.stat().st_size / 1_048_576
    print(f"\n✅ Built: {final}  ({size_mb:.1f} MB)")
    return final


# ════════════════════════════════════════════
# BACKEND 3: PYINSTALLER
# ════════════════════════════════════════════

def build_pyinstaller() -> Path:
    print(f"\n🔨 Building with PyInstaller...")
    ensure_dist()

    tag = platform_tag()
    out_name = f"{APP_NAME}-{tag}"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", out_name,
        "--workpath", str(BUILD_DIR),
        "--distpath", str(DIST_DIR),
        "--specpath", str(BUILD_DIR),
        "--clean", "--noconfirm",
        "--strip", "--noupx",
        "--onefile", "--console",
    ]

    for mod in [
        "fc", "fc.cli", "fc.panel", "fc.core", "fc.tree",
        "fc.output", "fc.clipboard", "fc.presets",
        "fc.config", "fc.colors", "fc.utils",
    ]:
        cmd.extend(["--hidden-import", mod])

    cmd.append(ENTRY_FILE)

    print(f"   Command: {' '.join(cmd)}\n")
    subprocess.check_call(cmd)

    suffix = ".exe" if platform.system() == "Windows" else ""
    exe = DIST_DIR / f"{out_name}{suffix}"

    if not exe.exists():
        raise FileNotFoundError(f"PyInstaller output not found: {exe}")

    make_executable(exe)
    size_mb = exe.stat().st_size / 1_048_576
    print(f"\n✅ Built: {exe}  ({size_mb:.1f} MB)")
    return exe


# ════════════════════════════════════════════
# BACKEND 4: DOCKER
# ════════════════════════════════════════════

def build_docker() -> Path:
    if not has_command("docker"):
        raise RuntimeError("Docker not installed")

    print(f"\n🐳 Building with Docker...")
    ensure_dist()

    dockerfile = BUILD_DIR / "Dockerfile.build"
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    dockerfile.write_text(dedent("""\
        FROM python:3.12-slim

        RUN apt-get update && \\
            apt-get install -y --no-install-recommends binutils && \\
            rm -rf /var/lib/apt/lists/*

        WORKDIR /build
        RUN pip install --no-cache-dir pyinstaller>=6.0

        COPY fc/ ./fc/
        COPY build.py .

        RUN python -m PyInstaller \\
            --name fc-linux-x86_64 \\
            --onefile --console --clean --noconfirm --strip --noupx \\
            --hidden-import fc --hidden-import fc.cli \\
            --hidden-import fc.panel --hidden-import fc.core \\
            --hidden-import fc.tree --hidden-import fc.output \\
            --hidden-import fc.clipboard --hidden-import fc.presets \\
            --hidden-import fc.config --hidden-import fc.colors \\
            --hidden-import fc.utils \\
            fc/__main__.py

        CMD ["sleep", "10"]
    """), encoding="utf-8")

    image_tag = "fc-builder"
    container_name = "fc-build-tmp"

    # Build image
    subprocess.check_call([
        "docker", "build",
        "-t", image_tag,
        "-f", str(dockerfile),
        ".",
    ])

    # Remove old container if exists
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
    )

    # Start container
    subprocess.check_call([
        "docker", "run", "-d",
        "--name", container_name,
        image_tag,
    ])

    # Copy binary out
    exe = DIST_DIR / "fc-linux-x86_64"
    try:
        subprocess.check_call([
            "docker", "cp",
            f"{container_name}:/build/dist/fc-linux-x86_64",
            str(exe),
        ])
    finally:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
        )

    if not exe.exists():
        raise FileNotFoundError("Docker build failed")

    make_executable(exe)
    size_mb = exe.stat().st_size / 1_048_576
    print(f"\n✅ Built: {exe}  ({size_mb:.1f} MB)")
    return exe


# ════════════════════════════════════════════
# INSTALL SCRIPTS
# ════════════════════════════════════════════

def create_install_scripts() -> None:
    ensure_dist()

    sh = DIST_DIR / "install.sh"
    sh.write_text(dedent("""\
        #!/bin/bash
        set -e
        DIR="$(cd "$(dirname "$0")" && pwd)"
        INSTALL_DIR="${HOME}/.local/bin"
        mkdir -p "$INSTALL_DIR"

        EXE=$(find "$DIR" -maxdepth 1 -name "fc-*" -type f ! -name "*.sh" ! -name "*.bat" ! -name "*.ps1" | head -1)
        PYZ=$(find "$DIR" -maxdepth 1 -name "*.pyz" -type f | head -1)

        if [ -n "$EXE" ]; then
            cp "$EXE" "$INSTALL_DIR/fc"
            chmod +x "$INSTALL_DIR/fc"
            echo "✅ Installed binary: $INSTALL_DIR/fc"
        elif [ -n "$PYZ" ]; then
            cp "$PYZ" "$INSTALL_DIR/fc.pyz"
            chmod +x "$INSTALL_DIR/fc.pyz"
            printf '#!/bin/sh\\nexec python3 "$(dirname "$0")/fc.pyz" "$@"\\n' > "$INSTALL_DIR/fc"
            chmod +x "$INSTALL_DIR/fc"
            echo "✅ Installed pyz: $INSTALL_DIR/fc"
        else
            echo "❌ No fc executable found in $DIR"
            exit 1
        fi

        if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
            RC=""
            [ -f "$HOME/.zshrc" ] && RC="$HOME/.zshrc"
            [ -f "$HOME/.bashrc" ] && RC="$HOME/.bashrc"
            if [ -n "$RC" ]; then
                echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$RC"
                echo "Added to PATH in $RC — restart terminal"
            fi
        fi
    """), encoding="utf-8")
    make_executable(sh)

    ps1 = DIST_DIR / "install.ps1"
    ps1.write_text(dedent("""\
        $dir = Split-Path -Parent $MyInvocation.MyCommand.Path
        $installDir = "$env:LOCALAPPDATA\\fc"
        New-Item -ItemType Directory -Force -Path $installDir | Out-Null

        $exe = Get-ChildItem "$dir\\fc-win-*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        $pyz = Get-ChildItem "$dir\\*.pyz" -ErrorAction SilentlyContinue | Select-Object -First 1

        if ($exe) {
            Copy-Item $exe.FullName "$installDir\\fc.exe" -Force
            Write-Host "Installed: $installDir\\fc.exe"
        } elseif ($pyz) {
            Copy-Item $pyz.FullName "$installDir\\fc.pyz" -Force
            Set-Content "$installDir\\fc.bat" "@echo off`r`npython `"%~dp0fc.pyz`" %*"
            Write-Host "Installed: $installDir\\fc.bat"
        } else {
            Write-Error "No fc executable found"; exit 1
        }

        $path = [Environment]::GetEnvironmentVariable("PATH", "User")
        if ($path -notlike "*$installDir*") {
            [Environment]::SetEnvironmentVariable("PATH", "$path;$installDir", "User")
            Write-Host "Added to PATH — restart terminal"
        }
    """), encoding="utf-8")

    print(f"📄 Install scripts created in {DIST_DIR}/")


# ════════════════════════════════════════════
# AUTO-SELECT
# ════════════════════════════════════════════

def auto_build() -> Path:
    print("🔍 Detecting best build backend...\n")

    print(f"  📦 zipapp      — ✅ always available")

    has_nuitka = False
    try:
        subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True, check=True,
        )
        has_nuitka = True
        print(f"  🔨 nuitka      — ✅ available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"  🔨 nuitka      — ❌ not installed")

    has_pi = False
    has_shared = python_has_shared_lib()
    try:
        import PyInstaller  # noqa: F401
        has_pi = True
        if has_shared:
            print(f"  🔨 pyinstaller — ✅ available")
        else:
            print(f"  🔨 pyinstaller — ⚠️  no --enable-shared")
    except ImportError:
        print(f"  🔨 pyinstaller — ❌ not installed")

    has_dock = has_command("docker")
    print(f"  🐳 docker      — {'✅' if has_dock else '❌'}")

    print()

    if has_nuitka:
        try:
            print("→ Trying Nuitka...")
            return build_nuitka()
        except Exception as e:
            print(f"  ⚠️  Nuitka failed: {e}\n")

    if has_pi and has_shared:
        try:
            print("→ Trying PyInstaller...")
            return build_pyinstaller()
        except Exception as e:
            print(f"  ⚠️  PyInstaller failed: {e}\n")

    if has_dock:
        try:
            print("→ Trying Docker...")
            return build_docker()
        except Exception as e:
            print(f"  ⚠️  Docker failed: {e}\n")

    print("→ Falling back to zipapp...")
    return build_zipapp()


# ════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Build fc executables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent("""\
            python build.py                Auto-detect best backend
            python build.py zipapp         Always works, needs python
            python build.py nuitka         Standalone binary
            python build.py pyinstaller    Classic (needs --enable-shared)
            python build.py docker         Linux binary via Docker
            python build.py clean          Remove build artifacts
        """),
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="auto",
        choices=["auto", "zipapp", "nuitka", "pyinstaller", "docker", "clean", "install-scripts"],
    )

    args = parser.parse_args()

    if args.action == "clean":
        clean()
        return

    if args.action == "install-scripts":
        create_install_scripts()
        return

    builders = {
        "auto": auto_build,
        "zipapp": build_zipapp,
        "nuitka": build_nuitka,
        "pyinstaller": build_pyinstaller,
        "docker": build_docker,
    }

    clean()
    try:
        builders[args.action]()
        create_install_scripts()

        if BUILD_DIR.exists():
            shutil.rmtree(BUILD_DIR)

        print(f"\n{'═' * 40}")
        print(f"🎉 Done! Files in ./{DIST_DIR}/")
        print(f"{'═' * 40}")

    except Exception as e:
        print(f"\n❌ Build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
