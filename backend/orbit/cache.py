"""Compatibility module alias; implementation lives in core.cache."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".core.cache", __package__)
