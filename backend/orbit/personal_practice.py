"""Compatibility module alias; implementation lives in features.personal_practice."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".features.personal_practice", __package__)
