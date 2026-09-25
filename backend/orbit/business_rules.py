"""Compatibility module alias; implementation lives in core.business_rules."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".core.business_rules", __package__)
