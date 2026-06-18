"""Tests for scripts/flavor.py: the shared flavor (game edition) resolution.

Run: python3 -m unittest discover -s tests -v   (from the wow-api repo root)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import flavor  # noqa: E402


class FlavorTest(unittest.TestCase):
    def test_canonical_flavors_mainline_first(self):
        flavors = flavor.canonical_flavors()
        self.assertEqual(flavors[0], "mainline")
        for f in ("era", "mists", "cata", "wrath"):
            self.assertIn(f, flavors)

    def test_from_project_id(self):
        self.assertEqual(flavor.flavor_from_project_id(1), "mainline")
        self.assertEqual(flavor.flavor_from_project_id(2), "era")
        self.assertEqual(flavor.flavor_from_project_id(11), "wrath")
        self.assertEqual(flavor.flavor_from_project_id(14), "cata")
        self.assertEqual(flavor.flavor_from_project_id("1"), "mainline")  # stringified
        self.assertIsNone(flavor.flavor_from_project_id(999))
        self.assertIsNone(flavor.flavor_from_project_id(None))

    def test_from_interface_ranges(self):
        self.assertEqual(flavor.flavor_from_interface(120007), "mainline")
        self.assertEqual(flavor.flavor_from_interface(11507), "era")
        self.assertEqual(flavor.flavor_from_interface(50500), "mists")
        self.assertEqual(flavor.flavor_from_interface(40400), "cata")
        self.assertEqual(flavor.flavor_from_interface(30403), "wrath")
        self.assertIsNone(flavor.flavor_from_interface(99999))  # below mainline floor
        self.assertIsNone(flavor.flavor_from_interface(None))

    def test_from_toc_filename_suffix(self):
        self.assertEqual(flavor.flavor_from_toc_filename("Foo.toc"), "mainline")
        self.assertEqual(flavor.flavor_from_toc_filename("Foo_Mainline.toc"), "mainline")
        self.assertEqual(flavor.flavor_from_toc_filename("Foo_Vanilla.toc"), "era")
        self.assertEqual(flavor.flavor_from_toc_filename("Foo_Classic.toc"), "era")
        self.assertEqual(flavor.flavor_from_toc_filename("Foo_Mists.toc"), "mists")
        self.assertEqual(flavor.flavor_from_toc_filename("Foo_Cata.toc"), "cata")
        self.assertEqual(flavor.flavor_from_toc_filename("Foo_Wrath.toc"), "wrath")
        # case-insensitive
        self.assertEqual(flavor.flavor_from_toc_filename("Foo_VANILLA.toc"), "era")
        # unknown suffix -> None (so resolve_toc_flavor can fall through)
        self.assertIsNone(flavor.flavor_from_toc_filename("Foo_Bar.toc"))
        # multi-underscore name: only the last segment is the flavor suffix
        self.assertEqual(flavor.flavor_from_toc_filename("My_Cool_Addon.toc"), None)
        self.assertEqual(flavor.flavor_from_toc_filename("My_Cool_Mists.toc"), "mists")

    def test_resolve_toc_flavor_precedence(self):
        # filename suffix wins outright
        self.assertEqual(flavor.resolve_toc_flavor("Foo_Vanilla.toc", 120007), "era")
        # unknown suffix -> interface tiebreak
        self.assertEqual(flavor.resolve_toc_flavor("Foo_Bar.toc", 11507), "era")
        # neither -> default mainline
        self.assertEqual(flavor.resolve_toc_flavor("Foo.toc", None), "mainline")
        self.assertEqual(flavor.resolve_toc_flavor("Foo_Bar.toc", None), "mainline")


if __name__ == "__main__":
    unittest.main()
