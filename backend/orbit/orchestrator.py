"""Compatibility module alias; implementation lives in ai.orchestrator."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".ai.orchestrator", __package__)
