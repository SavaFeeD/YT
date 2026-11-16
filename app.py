"""YT desktop entry point. Run with python app.py or preview.cmd."""
import argparse
import subprocess
import sys

# Keep the public downloader helpers available to scripts importing app.
from downloader import download, ffmpeg_path, playlist_url
from ui import App


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true', help='Check desktop startup and FFmpeg, then exit.')
    parser.add_argument('--playlist', help='Open a playlist preview without starting a download.')
    parser.add_argument('--audio-smoke-test', metavar='MP3', help='Check the MP3 decoder silently and exit.')
    args = parser.parse_args()
    if args.audio_smoke_test:
        from player import audio_smoke_test
        try:
            audio_smoke_test(args.audio_smoke_test)
        except Exception as error:
            if sys.stderr:
                print(error, file=sys.stderr)
            raise SystemExit(1)
        raise SystemExit(0)
    app = App(start_maximized=False if args.smoke_test else None, scan_on_start=not args.smoke_test)
    if args.smoke_test:
        app.withdraw()
        app.update()
        subprocess.run([ffmpeg_path(), '-version'], check=True, capture_output=True)
        app.destroy()
    else:
        if args.playlist:
            app.url.set(args.playlist)
            app.show_page('downloads')
        app.mainloop()
