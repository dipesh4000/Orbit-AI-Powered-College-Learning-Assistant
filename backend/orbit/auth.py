"""Compatibility module alias; implementation lives in api.auth."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".api.auth", __package__)
