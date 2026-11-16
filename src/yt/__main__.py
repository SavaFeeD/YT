"""CLI and desktop entry points for python -m yt and yt.exe."""

import argparse
import logging
import subprocess
import sys

from yt.infrastructure.runtime import app_version, ffmpeg_path, settings_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="YT music library and playlist downloader")
    parser.add_argument("--version", action="version", version=f"YT {app_version()}")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Check desktop and FFmpeg startup, then exit"
    )
    parser.add_argument(
        "--audio-smoke-test", metavar="MP3", help="Check the MP3 decoder silently, then exit"
    )
    parser.add_argument("--playlist", help="Preview a playlist without starting a download")
    args = parser.parse_args(argv)
    try:
        if args.audio_smoke_test:
            from yt.infrastructure.audio import audio_smoke_test

            audio_smoke_test(args.audio_smoke_test)
            return 0
        from yt.bootstrap import create_services
        from yt.infrastructure.logging import configure_logging
        from yt.presentation.window import ApplicationWindow

        if not args.smoke_test:
            configure_logging(settings_path().parent / "logs")
        app = ApplicationWindow(
            create_services(),
            start_maximized=False if args.smoke_test else None,
            scan_on_start=not args.smoke_test,
            persist_on_close=not args.smoke_test,
        )
        if args.smoke_test:
            app.withdraw()
            app.update()
            subprocess.run([ffmpeg_path(), "-version"], check=True, capture_output=True)
            app.destroy()
        else:
            if args.playlist:
                app.url.set(args.playlist)
                app.show_page("downloads")
            app.mainloop()
        return 0
    except Exception as error:
        logging.getLogger(__name__).exception("Application startup failed")
        if sys.stderr:
            print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
