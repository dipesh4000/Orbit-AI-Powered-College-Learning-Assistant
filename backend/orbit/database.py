"""Compatibility module alias; implementation lives in core.database."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".core.database", __package__)
