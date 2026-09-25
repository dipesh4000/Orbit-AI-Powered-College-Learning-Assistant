"""Compatibility module alias; implementation lives in features.personal."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".features.personal", __package__)
