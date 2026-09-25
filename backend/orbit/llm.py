"""Compatibility module alias; implementation lives in ai.llm."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".ai.llm", __package__)
