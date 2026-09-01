"""Provide application contexts, HTTP contracts, serving, and realtime infrastructure.

The package defines reusable execution boundaries without absorbing monoapp product policy.
"""
from monotools.runtime.monoform import monoform_operation

__all__ = ["monoform_operation"]
