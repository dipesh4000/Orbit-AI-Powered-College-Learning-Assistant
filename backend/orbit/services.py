"""Compatibility module alias; implementation lives in core.services."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".core.services", __package__)
