"""Compatibility module alias; implementation lives in core.telemetry."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".core.telemetry", __package__)
