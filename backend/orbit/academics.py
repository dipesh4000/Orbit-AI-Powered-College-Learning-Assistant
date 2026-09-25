"""Compatibility module alias; implementation lives in features.academics."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".features.academics", __package__)
