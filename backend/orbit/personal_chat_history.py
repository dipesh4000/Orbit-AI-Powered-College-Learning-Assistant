"""Compatibility module alias; implementation lives in features.personal_chat_history."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".features.personal_chat_history", __package__)
