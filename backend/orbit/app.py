"""Compatibility entry point for existing Uvicorn commands and integrations."""

from .main import app, services, sessions

__all__ = ["app", "services", "sessions"]
