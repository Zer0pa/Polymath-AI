"""Phase 0E / 0F / 0G / 1A experiment runners.

The single host- and Termux-facing entry point is
``polymath_ai.experiments.runner`` (invoked via
``python -m polymath_ai.experiments.runner``). It dispatches by ``--phase``
to phase-specific runners.
"""
