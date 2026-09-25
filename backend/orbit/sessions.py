"""Compatibility module alias; implementation lives in core.sessions."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".core.sessions", __package__)
