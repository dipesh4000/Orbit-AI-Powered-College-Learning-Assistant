"""Compatibility module alias; implementation lives in core.conversations."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".core.conversations", __package__)
