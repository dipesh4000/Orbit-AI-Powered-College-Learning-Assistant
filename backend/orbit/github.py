"""Compatibility module alias; implementation lives in features.github."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".features.github", __package__)
