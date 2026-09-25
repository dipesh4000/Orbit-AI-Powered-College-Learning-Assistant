"""Compatibility module alias; implementation lives in features.practice."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".features.practice", __package__)
