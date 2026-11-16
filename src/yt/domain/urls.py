"""Accepted playlist URL policy."""

from urllib.parse import parse_qs, urlparse


def playlist_url(value):
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https") or (parsed.hostname or "").lower() not in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
    ):
        raise ValueError("Вставьте ссылку на плейлист YouTube.")
    playlist = parse_qs(parsed.query).get("list", [""])[0]
    if not playlist or not all(c.isalnum() or c in "_-" for c in playlist):
        raise ValueError("В ссылке нет плейлиста (параметра list).")
    return "https://www.youtube.com/playlist?list=" + playlist
