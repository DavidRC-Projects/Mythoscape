"Unit tests for the visual building-verification script."""
import builtins
import contextlib
import io
import os
import runpy
import sys
import types
import unittest
from unittest import mock
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_building_fix.py")

class FakeImage:
    def get_size(self):
        return (320, 180)

class FakeSurface:
    def __init__(self, size=None):
        self.size = size
    def get_size(self):
        return self.size
    def fill(self, color):
        self.fill_color = color
    def blit(self, source, position):
        pass
class FakePygame(types.ModuleType):
    QUIT = 1
    KEYDOWN = 2
    K_ESCAPE = 27
    error = RuntimeError
    def __init__(self, events, image_error=None):
        super().__init__("pygame")
        self.events = events
        self.image_error = image_error
        self.init = mock.Mock()
        self.quit = mock.Mock()
        self.image = types.SimpleNamespace(load=mock.Mock(side_effect=self._load_image))
        self.display = types.SimpleNamespace(
            set_mode=mock.Mock(return_value=FakeSurface()),
            set_caption=mock.Mock(),
            flip=mock.Mock(),
        )
        self.Surface = mock.Mock(side_effect=FakeSurface)
        self.font = types.SimpleNamespace(Font=mock.Mock(return_value=mock.Mock(render=mock.Mock(return_value=object()))))
        self.time = types.SimpleNamespace(Clock=mock.Mock(return_value=mock.Mock(tick=mock.Mock())))
        self.event = types.SimpleNamespace(get=mock.Mock(side_effect=self._get_events))

    def _load_image(self, path):
        if self.image_error is not None:
            raise self.image_error
        return FakeImage()

    def _get_events(self):
        return self.events.pop(0) if self.events else []

class VerifyBuildingFixTests(unittest.TestCase):
    def run_script(self, pygame_module, asset_exists=True):
        asset_path = os.path.join(
            os.path.dirname(SCRIPT_PATH),
            "game", "assets", "mmorpg", "client", "assets", "buildings", "void_sanctum.png",
        )
        real_exists = os.path.exists
        exists = lambda path: asset_exists if path == asset_path else real_exists(path)
        with mock.patch.object(os.path, "exists", side_effect=exists):
            with mock.patch.dict(sys.modules, {"pygame": pygame_module}):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    try:
                        runpy.run_path(SCRIPT_PATH, run_name="__main__")
                    except SystemExit as error:
                        return output.getvalue(), error.code
        return output.getvalue(), None
    def run_without_pygame(self):
        real_import = builtins.__import__

        def import_without_pygame(name, *args, **kwargs):
            if name == "pygame":
                raise ImportError("pygame unavailable")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=import_without_pygame):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                try:
                    runpy.run_path(SCRIPT_PATH, run_name="__main__")
                except SystemExit as error:
                    return output.getvalue(), error.code
        self.fail("Script did not exit when pygame was unavailable")


    def test_successfully_displays_image_and_exits_on_window_close(self):
        pygame = FakePygame(events=[[types.SimpleNamespace(type=FakePygame.QUIT)]])

        output, exit_code = self.run_script(pygame)

        self.assertIsNone(exit_code)
        pygame.init.assert_called_once_with()
        pygame.image.load.assert_called_once()
        pygame.display.set_mode.assert_called_once_with((360, 280))
        pygame.display.set_caption.assert_called_once_with(
            "Mythoscape - Building Rendering Fix Verification"
        )
        pygame.display.flip.assert_called_once_with()
        pygame.time.Clock.return_value.tick.assert_called_once_with(30)
        pygame.quit.assert_called_once_with()
        self.assertIn("Loaded void_sanctum.png: 320x180 pixels", output)
        self.assertIn("Verification complete!", output)

    def test_ignores_unrelated_key_and_exits_on_escape(self):
        pygame = FakePygame(
            events=[
                [types.SimpleNamespace(type=FakePygame.KEYDOWN, key=65)],
                [types.SimpleNamespace(type=FakePygame.KEYDOWN, key=FakePygame.K_ESCAPE)],
            ]
        )

        output, exit_code = self.run_script(pygame)

        self.assertIsNone(exit_code)
        self.assertEqual(pygame.display.flip.call_count, 2)
        self.assertEqual(pygame.time.Clock.return_value.tick.call_count, 2)
        pygame.quit.assert_called_once_with()

    def test_missing_asset_exits_with_actionable_error_before_initializing_pygame(self):
        pygame = FakePygame(events=[])

        output, exit_code = self.run_script(pygame, asset_exists=False)

        self.assertEqual(exit_code, 1)
        self.assertIn("ERROR: void_sanctum.png not found at", output)
        pygame.init.assert_not_called()
        pygame.image.load.assert_not_called()

    def test_image_loading_error_is_reported_and_exits(self):
        pygame = FakePygame(events=[], image_error=RuntimeError("corrupt image"))

        output, exit_code = self.run_script(pygame)

        self.assertEqual(exit_code, 1)
        self.assertIn("ERROR loading void_sanctum.png: corrupt image", output)
        pygame.quit.assert_not_called()

    def test_missing_pygame_dependency_reports_install_instruction(self):
        output, exit_code = self.run_without_pygame()

        self.assertEqual(exit_code, 1)
        self.assertIn("ERROR: pygame not installed", output)
        self.assertIn("Install with: pip3 install pygame", output)

if __name__ == "__main__":
    unittest.main()
