"""Compatibility module alias; implementation lives in api.workspace_api."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".api.workspace_api", __package__)
