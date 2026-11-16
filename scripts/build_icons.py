"""Render native icon sizes from public/app-icon.svg. Install resvg-py to regenerate."""

import struct
from pathlib import Path

import resvg_py

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "public"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
source = (ASSETS / "app-icon.svg").read_text(encoding="utf-8")
frames = [resvg_py.svg_to_bytes(svg_string=source, width=size, height=size) for size in SIZES]
header = struct.pack("<HHH", 0, 1, len(frames))
offset = len(header) + len(frames) * 16
entries = []
for size, frame in zip(SIZES, frames, strict=True):
    entries.append(
        struct.pack(
            "<BBBBHHII",
            size if size < 256 else 0,
            size if size < 256 else 0,
            0,
            0,
            1,
            32,
            len(frame),
            offset,
        )
    )
    offset += len(frame)
(ASSETS / "favicon.ico").write_bytes(header + b"".join(entries) + b"".join(frames))
(ASSETS / "app-icon.png").write_bytes(
    resvg_py.svg_to_bytes(svg_string=source, width=1024, height=1024)
)
print("Saved public/favicon.ico and public/app-icon.png from public/app-icon.svg")
