"""Validated preferences, compatible with the original settings.json schema."""

import math
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    folder: str = field(default_factory=lambda: str(Path.home() / "Music" / "YT"))
    quality: str = "192"
    concurrency: int = 3
    volume: float = 0.5
    shuffle: bool = False
    url: str = ""
    library_folder: str = ""
    library_follow: bool = True
    maximized: bool = True
    extra: dict[str, object] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, data: object) -> "AppSettings":
        if not isinstance(data, dict):
            return cls()
        defaults = cls()
        values = {}
        for name in ("folder", "url", "library_folder"):
            value = data.get(name)
            values[name] = (
                value if isinstance(value, str) and "\x00" not in value else getattr(defaults, name)
            )
        if not values["folder"].strip():
            values["folder"] = defaults.folder
        quality = str(data.get("quality", defaults.quality))
        values["quality"] = quality if quality in {"128", "192", "256", "320"} else defaults.quality
        try:
            concurrency = int(data.get("concurrency", defaults.concurrency))
            values["concurrency"] = concurrency if 1 <= concurrency <= 6 else defaults.concurrency
        except (ValueError, TypeError, OverflowError):
            values["concurrency"] = defaults.concurrency
        try:
            volume = float(data.get("volume", defaults.volume))
            values["volume"] = max(0, min(1, volume)) if math.isfinite(volume) else defaults.volume
        except (ValueError, TypeError, OverflowError):
            values["volume"] = defaults.volume
        for name in ("shuffle", "library_follow", "maximized"):
            value = data.get(name)
            values[name] = value if isinstance(value, bool) else getattr(defaults, name)
        known = set(cls.__dataclass_fields__)
        values["extra"] = {key: value for key, value in data.items() if key not in known}
        return cls(**values)

    def to_mapping(self) -> dict[str, object]:
        return {
            **self.extra,
            **{name: getattr(self, name) for name in self.__dataclass_fields__ if name != "extra"},
        }
