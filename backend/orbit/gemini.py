"""Compatibility module alias; implementation lives in ai.gemini."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".ai.gemini", __package__)
