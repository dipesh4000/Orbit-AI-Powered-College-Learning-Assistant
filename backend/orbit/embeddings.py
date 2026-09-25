"""Compatibility module alias; implementation lives in ai.embeddings."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module(".ai.embeddings", __package__)
