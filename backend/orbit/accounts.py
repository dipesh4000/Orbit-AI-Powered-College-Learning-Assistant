"""Compatibility module alias; implementation lives in core.accounts."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".core.accounts", __package__)
