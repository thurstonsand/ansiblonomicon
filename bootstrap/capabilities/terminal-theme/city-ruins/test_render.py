"""Check the colour contracts consumed by Windows and WezTerm."""

import configparser
import tomllib
import unittest

from render import wezterm, windows_theme


class WindowsThemeTest(unittest.TestCase):
    def test_windows_uses_argb_and_explicit_app_and_system_modes(self) -> None:
        for mode, expected in (("dark", "Dark"), ("light", "Light")):
            with self.subTest(mode=mode):
                theme = configparser.ConfigParser(interpolation=None)
                theme.read_string(
                    windows_theme({"mode": mode, "accent": "#123abc"}, "Example")
                )
                self.assertEqual(theme["Theme"]["DisplayName"], "Example")
                self.assertEqual(
                    int(theme["VisualStyles"]["ColorizationColor"], 16), 0xC4123ABC
                )
                self.assertEqual(theme["VisualStyles"]["AppMode"], expected)
                self.assertEqual(theme["VisualStyles"]["SystemMode"], expected)
                self.assertEqual(theme["VisualStyles"]["AutoColorization"], "0")

    def test_wezterm_maps_ansi_slots_and_readable_cursor_and_tabs(self) -> None:
        palette = {
            "background": "#010203",
            "foreground": "#aabbcc",
            "dark_background": "#000102",
            "accent": "#123abc",
            "selection": "#102030",
            "muted": "#404142",
            "bright_foreground": "#ddeeff",
            "red": "#a10000",
            "green": "#00a200",
            "yellow": "#a3a300",
            "blue": "#0000a4",
            "magenta": "#a500a5",
            "cyan": "#00a6a6",
            "bright_red": "#b10000",
            "bright_green": "#00b200",
            "bright_yellow": "#b3b300",
            "bright_blue": "#0000b4",
            "bright_magenta": "#b500b5",
            "bright_cyan": "#00b6b6",
        }
        scheme = tomllib.loads(wezterm(palette, "Example"))
        self.assertEqual(scheme["metadata"]["name"], "Example")
        colors = scheme["colors"]
        self.assertEqual(
            colors["ansi"],
            [
                "#010203",
                "#a10000",
                "#00a200",
                "#a3a300",
                "#0000a4",
                "#a500a5",
                "#00a6a6",
                "#aabbcc",
            ],
        )
        self.assertEqual(
            colors["brights"],
            [
                "#404142",
                "#b10000",
                "#00b200",
                "#b3b300",
                "#0000b4",
                "#b500b5",
                "#00b6b6",
                "#ddeeff",
            ],
        )
        self.assertEqual(colors["cursor_bg"], "#ddeeff")
        self.assertEqual(colors["cursor_fg"], "#010203")
        self.assertEqual(colors["selection_bg"], "#102030")
        self.assertEqual(
            colors["tab_bar"]["active_tab"],
            {"bg_color": "#123abc", "fg_color": "#010203"},
        )


if __name__ == "__main__":
    unittest.main()
