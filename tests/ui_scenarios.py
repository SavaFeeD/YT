import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from yt.bootstrap import create_services
from yt.domain.music import Track
from yt.presentation.window import ApplicationWindow


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        services = create_services(settings_file=Path(self.temp.name) / "settings.json")
        self.images = patch.object(services.thumbnails, "load")
        self.images.start()
        self.app = ApplicationWindow(services, start_maximized=False, scan_on_start=False)
        self.app.withdraw()
        self.app.show_playlist(
            {
                "url": "https://www.youtube.com/playlist?list=test",
                "title": "Test playlist",
                "thumbnail": None,
                "entries": [
                    {
                        "key": "1:a",
                        "id": "a",
                        "title": "Луна",
                        "duration": 120,
                        "available": True,
                        "thumbnail": None,
                    },
                    {
                        "key": "2:b",
                        "id": "b",
                        "title": "Звёзды",
                        "duration": None,
                        "available": True,
                        "thumbnail": None,
                    },
                ],
            }
        )
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.images.stop()
        self.temp.cleanup()

    def test_search_and_updates_for_hidden_track(self):
        self.app.search.set("ЛУНА")
        self.assertEqual(self.app.rows["1:a"].winfo_manager(), "pack")
        self.assertEqual(self.app.rows["2:b"].winfo_manager(), "")
        self.app.handle_event("track", {"key": "2:b", "state": "done", "percent": 100})
        self.app.search.set("")
        self.assertEqual(self.app.rows["2:b"].state, "done")
        self.assertEqual(self.app.rows["2:b"].winfo_manager(), "pack")

    def test_busy_controls_and_final_error_state(self):
        self.app.set_busy(True)
        self.assertEqual(self.app.download_view.start_button.cget("state"), "disabled")
        self.assertEqual(self.app.download_view.stop_button.cget("state"), "normal")
        self.app.handle_event("track", {"key": "1:a", "state": "error"})
        self.app.handle_event("done", "Завершено с ошибками.")
        self.assertEqual(self.app.download_view.start_button.cget("state"), "normal")
        self.assertEqual(self.app.rows["1:a"].state, "error")
        self.assertEqual(self.app.rows["2:b"].state, "stopped")

    def test_old_preview_cannot_replace_new_playlist(self):
        self.app.preview_token = 3
        self.app.handle_event("preview", (2, None, "Old request failed"))
        self.assertEqual(self.app.playlist_title.get(), "Test playlist")

    def test_parallel_speed_is_summed_and_finished_track_is_removed(self):
        self.app.handle_event(
            "track", {"key": "1:a", "state": "downloading", "percent": 10, "speed": 2 * 1048576}
        )
        self.app.handle_event(
            "track", {"key": "2:b", "state": "downloading", "percent": 20, "speed": 3 * 1048576}
        )
        self.assertIn("5.0 МБ/с", self.app.detail.get())
        self.assertIn("Активно 2", self.app.detail.get())
        self.app.handle_event("track", {"key": "1:a", "state": "done"})
        self.assertIn("3.0 МБ/с", self.app.detail.get())
        self.app.set_busy(True)
        self.assertEqual(self.app.download_view.concurrency_buttons["3"].cget("state"), "disabled")

    def test_library_plays_local_selection_while_downloads_are_busy(self):
        from tests.fakes import FakeBackend

        self.app.player.backend = FakeBackend()
        tracks = [Track(Path(self.temp.name) / "song.mp3", "Моя песня", duration=120)]
        library = self.app.library
        library.token = 1
        library.apply((1, self.temp.name, tracks, 0, None))
        self.app.set_busy(True)
        library.tree.selection_set(tracks[0].key)
        library.play_selected()
        self.assertEqual(self.app.player.state, "playing")
        self.app.show_page("downloads")
        self.assertEqual(self.app.player.state, "playing")
        self.app.show_page("library")
        self.assertEqual(self.app.player.current, tracks[0])

    def test_volume_shuffle_settings_persist_and_small_player_is_not_clipped(self):
        import json

        self.app.player_bar.change_volume(27)
        self.app.player_bar.toggle_shuffle()
        self.app.save_settings()
        saved = json.loads((Path(self.temp.name) / "settings.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(saved["volume"], 0.27)
        self.assertTrue(saved["shuffle"])
        for width, height in ((1280, 720), (1920, 1080)):
            self.app.geometry(f"{width}x{height}")
            self.app.deiconify()
            self.app.update()
            bar = self.app.player_bar
            self.assertGreater(bar.winfo_height(), 70)
            self.assertLessEqual(bar.winfo_y() + bar.winfo_height(), self.app.winfo_height())
            self.assertLessEqual(bar.mute.winfo_rootx(), self.app.winfo_rootx() + width)
            self.assertLessEqual(bar.winfo_reqwidth(), width)
