"""Compatibility module alias and entry point for demo dataset ingestion."""

if __name__ == "__main__":
    from .ai.ingest import main

    main()
else:
    import sys
    from importlib import import_module

    sys.modules[__name__] = import_module(".ai.ingest", __package__)
