"""YT desktop entry point. Run with python app.py or preview.cmd."""
import argparse
import subprocess

# Keep the public downloader helpers available to scripts importing app.
from downloader import download, ffmpeg_path, playlist_url
from ui import App


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true', help='Check desktop startup and FFmpeg, then exit.')
    parser.add_argument('--playlist', help='Open a playlist preview without starting a download.')
    args = parser.parse_args()
    app = App()
    if args.smoke_test:
        app.withdraw()
        app.update()
        subprocess.run([ffmpeg_path(), '-version'], check=True, capture_output=True)
        app.destroy()
    else:
        if args.playlist:
            app.url.set(args.playlist)
        app.mainloop()
