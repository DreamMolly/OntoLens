"""Compatibility imports for releases published under the former package name.

Active code lives in :mod:`ontolens`. Aliases load lazily so a CLI-only install
does not import optional web dependencies, and every alias shares the canonical
module, class and runtime state instead of loading a second implementation.
"""
from importlib import import_module
from importlib.abc import Loader, MetaPathFinder
from importlib.util import find_spec, spec_from_loader
import sys


class _AliasLoader(Loader):
    def __init__(self, canonical):
        self.canonical = canonical

    def create_module(self, spec):
        module = import_module(self.canonical)
        self.canonical_spec = module.__spec__
        return module

    def exec_module(self, module):
        # importlib initializes an alias spec; restore canonical metadata.
        module.__spec__ = self.canonical_spec


class _AliasFinder(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith("peiwu.") or fullname == "peiwu.__main__":
            return None
        canonical = "ontolens." + fullname[len("peiwu."):]
        canonical_spec = find_spec(canonical)
        if canonical_spec is None:
            return None
        return spec_from_loader(fullname, _AliasLoader(canonical),
                                is_package=canonical_spec.submodule_search_locations is not None)


sys.meta_path.insert(0, _AliasFinder())
sys.modules[__name__] = import_module("ontolens")
