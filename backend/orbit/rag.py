"""Compatibility module alias and entry point for retrieval indexing."""

if __name__ == "__main__":
    import runpy

    runpy.run_module("orbit.ai.rag", run_name="__main__")
else:
    import sys
    from importlib import import_module

    sys.modules[__name__] = import_module(".ai.rag", __package__)
