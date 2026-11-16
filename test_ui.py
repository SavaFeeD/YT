from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ui import App


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = patch('ui.CONFIG', Path(self.temp.name) / 'settings.json')
        self.config.start()
        self.images = patch.object(App, 'load_images')
        self.images.start()
        self.app = App()
        self.app.withdraw()
        self.app.show_playlist({
            'url': 'https://www.youtube.com/playlist?list=test', 'title': 'Test playlist',
            'thumbnail': None,
            'entries': [
                {'key': '1:a', 'id': 'a', 'title': 'Луна', 'duration': 120, 'available': True, 'thumbnail': None},
                {'key': '2:b', 'id': 'b', 'title': 'Звёзды', 'duration': None, 'available': True, 'thumbnail': None},
            ],
        })
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.images.stop()
        self.config.stop()
        self.temp.cleanup()

    def test_search_and_updates_for_hidden_track(self):
        self.app.search.set('ЛУНА')
        self.assertEqual(self.app.rows['1:a'].winfo_manager(), 'pack')
        self.assertEqual(self.app.rows['2:b'].winfo_manager(), '')
        self.app.handle_event('track', {'key': '2:b', 'state': 'done', 'percent': 100})
        self.app.search.set('')
        self.assertEqual(self.app.rows['2:b'].state, 'done')
        self.assertEqual(self.app.rows['2:b'].winfo_manager(), 'pack')

    def test_busy_controls_and_final_error_state(self):
        self.app.set_busy(True)
        self.assertEqual(self.app.start_button.cget('state'), 'disabled')
        self.assertEqual(self.app.stop_button.cget('state'), 'normal')
        self.app.handle_event('track', {'key': '1:a', 'state': 'error'})
        self.app.handle_event('done', 'Завершено с ошибками.')
        self.assertEqual(self.app.start_button.cget('state'), 'normal')
        self.assertEqual(self.app.rows['1:a'].state, 'error')
        self.assertEqual(self.app.rows['2:b'].state, 'stopped')

    def test_old_preview_cannot_replace_new_playlist(self):
        self.app.preview_token = 3
        self.app.handle_event('preview', (2, None, 'Old request failed'))
        self.assertEqual(self.app.playlist_title.get(), 'Test playlist')

    def test_parallel_speed_is_summed_and_finished_track_is_removed(self):
        self.app.handle_event('track', {'key': '1:a', 'state': 'downloading', 'percent': 10, 'speed': 2 * 1048576})
        self.app.handle_event('track', {'key': '2:b', 'state': 'downloading', 'percent': 20, 'speed': 3 * 1048576})
        self.assertIn('5.0 МБ/с', self.app.detail.get())
        self.assertIn('Активно 2', self.app.detail.get())
        self.app.handle_event('track', {'key': '1:a', 'state': 'done'})
        self.assertIn('3.0 МБ/с', self.app.detail.get())
        self.app.set_busy(True)
        self.assertEqual(self.app.concurrency_buttons['3'].cget('state'), 'disabled')
