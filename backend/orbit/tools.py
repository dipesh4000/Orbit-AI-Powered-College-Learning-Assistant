"""Compatibility module alias; implementation lives in ai.tools."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".ai.tools", __package__)
