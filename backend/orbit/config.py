"""Compatibility module alias; implementation lives in core.config."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".core.config", __package__)
