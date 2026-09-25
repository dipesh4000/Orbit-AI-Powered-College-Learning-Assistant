"""Compatibility module alias; implementation lives in features.insights."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".features.insights", __package__)
