r"""Build YT and its installer: .venv\Scripts\python.exe build.py."""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_version():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version):
        raise SystemExit("VERSION must contain a version such as 0.1.0.")
    return version


def find_compiler():
    configured = os.environ.get("INNO_SETUP_COMPILER")
    candidates = (
        [configured]
        if configured
        else [
            str(ROOT / "tools" / "Inno" / "ISCC.exe"),
            shutil.which("ISCC.exe"),
            str(
                Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
                / "Inno Setup 6"
                / "ISCC.exe"
            ),
            str(
                Path(os.environ.get("ProgramFiles", "C:/Program Files"))
                / "Inno Setup 7"
                / "ISCC.exe"
            ),
        ]
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    raise SystemExit(
        "Inno Setup not found. Install it, use tools/Inno, or set INNO_SETUP_COMPILER to ISCC.exe."
    )


def check_tools():
    if sys.platform != "win32" or sys.version_info < (3, 11):
        raise SystemExit("Building requires Windows and Python 3.11+ (recommended: 3.13).")
    compiler = find_compiler()
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node.js 22+ must be available in PATH.")
    version = subprocess.check_output([node, "--version"], text=True).strip()
    if int(version.lstrip("v").split(".")[0]) < 22:
        raise SystemExit("Node.js 22+ is required.")
    return compiler, node


def package_release(version):
    release = ROOT / "release"
    installer = release / "YT-Setup.exe"
    if not installer.is_file():
        raise SystemExit("The installer was not created.")
    archive = Path(
        shutil.make_archive(
            str(release / f"YT-{version}-windows-x64"),
            "zip",
            root_dir=ROOT / "dist",
            base_dir="YT",
        )
    )
    checksums = []
    for artifact in (installer, archive):
        with artifact.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        checksums.append(f"{digest}  {artifact.name}\n")
    (release / "SHA256SUMS.txt").write_text("".join(checksums), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Check version and build tools without building."
    )
    args = parser.parse_args()
    version = read_version()
    compiler, node = check_tools()
    icon = ROOT / "public" / "favicon.ico"
    if not icon.is_file():
        raise SystemExit("Application icon not found: public/favicon.ico")
    print(f"YT {version}; Inno Setup: {compiler}; Node.js: {node}", flush=True)
    if args.check:
        return

    import imageio_ffmpeg

    binary_dir = ROOT / "build" / "runtime"
    binary_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), binary_dir / "ffmpeg.exe")
    shutil.copy2(node, binary_dir / "node.exe")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onedir",
            "--name",
            "YT",
            "--paths",
            str(ROOT / "src"),
            "--workpath",
            str(ROOT / "build" / "pyinstaller"),
            "--specpath",
            str(ROOT / "build" / "spec"),
            "--distpath",
            str(ROOT / "dist"),
            "--collect-all",
            "yt_dlp",
            "--collect-all",
            "yt_dlp_ejs",
            "--icon",
            str(icon),
            "--add-data",
            f"{icon};public",
            "--collect-binaries",
            "pygame",
            "--copy-metadata",
            "pygame-ce",
            "--copy-metadata",
            "yt-desktop",
            "--add-data",
            f"{ROOT / 'VERSION'};.",
            "--add-binary",
            f"{binary_dir / 'ffmpeg.exe'};bin",
            "--add-binary",
            f"{binary_dir / 'node.exe'};bin",
            "--exclude-module",
            "imageio_ffmpeg",
            str(ROOT / "app.py"),
        ],
        cwd=ROOT,
        check=True,
    )
    icon_name = f"YT-{hashlib.sha256(icon.read_bytes()).hexdigest()[:16]}.ico"
    subprocess.run(
        [
            str(compiler),
            f"/DMyAppVersion={version}",
            f"/DMyAppIconName={icon_name}",
            str(ROOT / "installer.iss"),
        ],
        cwd=ROOT,
        check=True,
    )
    package_release(version)
    print(f"Release files: {ROOT / 'release'}", flush=True)


if __name__ == "__main__":
    main()
