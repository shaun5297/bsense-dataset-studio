import unittest

from bsense_dataset_studio.app import theme


class ThemeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original = theme.mode()

    def tearDown(self) -> None:
        theme.set_mode(self._original)

    def test_default_mode_is_dark(self) -> None:
        theme.set_mode("dark")
        self.assertEqual(theme.mode(), "dark")

    def test_color_roles_exist_in_both_modes(self) -> None:
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            for role in ("bg", "fg", "field", "border", "secondary", "muted", "accent"):
                self.assertRegex(theme.color(role), r"^#[0-9A-Fa-f]{6}$")

    def test_set_mode_rejects_unknown_mode(self) -> None:
        with self.assertRaises(ValueError):
            theme.set_mode("blue")

    def test_listeners_are_notified_on_change(self) -> None:
        seen = []
        theme.on_change(seen.append)
        try:
            theme.set_mode("light")
            theme.set_mode("dark")
        finally:
            theme._listeners.remove(seen.append)
        self.assertEqual(seen, ["light", "dark"])

    def test_light_and_dark_palettes_differ(self) -> None:
        theme.set_mode("light")
        light_bg = theme.color("bg")
        theme.set_mode("dark")
        self.assertNotEqual(light_bg, theme.color("bg"))


if __name__ == "__main__":
    unittest.main()
