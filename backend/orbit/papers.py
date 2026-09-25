"""Compatibility module alias; implementation lives in features.papers."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".features.papers", __package__)
