"""Compatibility module alias; implementation lives in features.projects."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".features.projects", __package__)
