# -*- coding: utf-8 -*-
"""Exceptions raised by the ladder package."""

from __future__ import annotations


class LadderError(Exception):
    """Base class for all ladder errors."""


class ConfigurationError(LadderError):
    """Invalid configuration or missing dependency."""


class SourceError(LadderError):
    """The time-series source could not satisfy a request."""


class StoreError(LadderError):
    """The point store could not satisfy a request."""


class CancelledError(LadderError):
    """The caller asked to stop the operation."""
