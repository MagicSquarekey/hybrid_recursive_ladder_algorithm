# -*- coding: utf-8 -*-
"""Shared fixtures."""

from __future__ import annotations

import pytest
from helpers import build_source, ms

from hybrid_ladder import LadderEngine, MemoryStore
from hybrid_ladder.models import LadderConfig


@pytest.fixture
def clock():
    """A clock far enough in the future that demo/materialize ranges are closed."""
    return lambda: ms(2030, 1, 1)


@pytest.fixture
def ten_days():
    return build_source()


@pytest.fixture
def engine(ten_days):
    source, _, _ = ten_days
    return LadderEngine(source)


@pytest.fixture
def mixed_engine(ten_days, clock):
    source, _, _ = ten_days
    store = MemoryStore()
    return LadderEngine(source, store, LadderConfig(), clock=clock)
