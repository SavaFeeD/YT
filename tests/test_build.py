import hashlib
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import build_release as build


class ReleaseTests(unittest.TestCase):
    def test_version_accepts_release_and_rejects_invalid_values(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(build, "ROOT", Path(directory)),
        ):
            version_file = Path(directory) / "VERSION"
            version_file.write_text("0.1.0\n", encoding="utf-8")
            self.assertEqual(build.read_version(), "0.1.0")
            for value in ("v0.1.0", "1.0", "../bad", "01.0.0", "1.2.3\nother"):
                with self.subTest(value=value):
                    version_file.write_text(value, encoding="utf-8")
                    with self.assertRaises(SystemExit):
                        build.read_version()

    def test_release_zip_and_checksums(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(build, "ROOT", Path(directory)),
        ):
            root = Path(directory)
            (root / "release").mkdir()
            (root / "release" / "YT-Setup.exe").write_bytes(b"installer fixture")
            (root / "dist" / "YT" / "_internal").mkdir(parents=True)
            (root / "dist" / "YT" / "YT.exe").write_bytes(b"app fixture")
            (root / "dist" / "YT" / "_internal" / "data.txt").write_text("data", encoding="utf-8")
            build.package_release("0.1.0")
            with zipfile.ZipFile(root / "release" / "YT-0.1.0-windows-x64.zip") as archive:
                self.assertEqual(archive.read("YT/YT.exe"), b"app fixture")
                self.assertEqual(archive.read("YT/_internal/data.txt"), b"data")
            lines = (root / "release" / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            for line in lines:
                digest, name = line.split("  ")
                self.assertEqual(
                    digest, hashlib.sha256((root / "release" / name).read_bytes()).hexdigest()
                )

    def test_missing_installer_cannot_be_packaged(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(build, "ROOT", Path(directory)),
        ):
            with self.assertRaises(SystemExit):
                build.package_release("0.1.0")

    def test_explicit_compiler_path(self):
        with tempfile.TemporaryDirectory() as directory:
            compiler = Path(directory) / "ISCC.exe"
            compiler.touch()
            with patch.dict(os.environ, {"INNO_SETUP_COMPILER": str(compiler)}):
                self.assertEqual(build.find_compiler(), compiler.resolve())
            with patch.dict(os.environ, {"INNO_SETUP_COMPILER": str(compiler) + ".missing"}):
                with self.assertRaises(SystemExit):
                    build.find_compiler()


if __name__ == "__main__":
    unittest.main()
