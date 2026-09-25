"""Compatibility module alias; implementation lives in features.coding."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".features.coding", __package__)
