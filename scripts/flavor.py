#!/usr/bin/env python3
"""Single source of truth for WoW flavor (game edition) resolution.

A "flavor" is a WoW edition with its own API surface: mainline (retail), era
(Classic Era / Vanilla), mists (MoP Classic), cata, wrath, tbc. The data lives in
config/flavors.json so the Python generators here and AddonSentry (which ships this
module via `COPY wow-api /opt/wow-api`) agree on the mapping without drifting.

Two runtime signals identify a flavor:
  * in-game: the global WOW_PROJECT_ID (captured by /papidump) -> flavor_from_project_id
  * an addon repo: the TOC filename suffix (Foo_Vanilla.toc) with the `## Interface:`
    number as a tiebreak -> resolve_toc_flavor

Build data is keyed `build/<flavor>/<interface>/`. PTR/Beta are not separate flavors;
they publish under their flavor with a higher interface number.
"""
import json
import os

DEFAULT_FLAVOR = "mainline"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FLAVORS_PATH = os.path.join(_REPO_ROOT, "config", "flavors.json")

_cache = None


def load_flavors(path=None):
    """Return the list of flavor records from flavors.json (cached)."""
    global _cache
    if path is None and _cache is not None:
        return _cache
    with open(path or _FLAVORS_PATH, encoding="utf-8") as fh:
        flavors = json.load(fh)["flavors"]
    if path is None:
        _cache = flavors
    return flavors


def canonical_flavors():
    """Ordered list of flavor ids (mainline first)."""
    return [f["id"] for f in load_flavors()]


def flavor_from_project_id(pid):
    """Map an in-game WOW_PROJECT_ID to a flavor id, or None if unknown."""
    if pid is None:
        return None
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    for f in load_flavors():
        if f.get("project_id") == pid:
            return f["id"]
    return None


def flavor_from_interface(interface):
    """Map an interface number (e.g. 120007) to a flavor id by range, or None."""
    if interface is None:
        return None
    try:
        interface = int(interface)
    except (TypeError, ValueError):
        return None
    for f in load_flavors():
        if f["interface_min"] <= interface <= f["interface_max"]:
            return f["id"]
    return None


def flavor_from_toc_filename(name):
    """Map a TOC filename to a flavor id by its suffix, or None if no suffix matches.

    'Foo.toc' / 'Foo_Mainline.toc' -> mainline; 'Foo_Vanilla.toc' -> era; etc.
    Suffix matching is case-insensitive. A bare name (no underscore suffix) is mainline.
    """
    base = os.path.basename(name)
    if base.lower().endswith(".toc"):
        base = base[:-4]
    suffix = base.rsplit("_", 1)[1] if "_" in base else ""
    suffix_l = suffix.lower()
    for f in load_flavors():
        for alias in f["aliases_toc"]:
            if alias.lower() == suffix_l:
                return f["id"]
    return None


def resolve_toc_flavor(filename, interface=None):
    """Resolve a TOC file's flavor: filename suffix first, interface as tiebreak.

    Falls back to the interface range when the filename suffix is unrecognized, and
    to mainline when neither yields a flavor (the common single-TOC retail case).
    """
    by_name = flavor_from_toc_filename(filename)
    if by_name is not None:
        return by_name
    by_iface = flavor_from_interface(interface)
    if by_iface is not None:
        return by_iface
    return DEFAULT_FLAVOR
