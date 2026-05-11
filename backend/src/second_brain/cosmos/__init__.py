"""Cosmos-document helpers (Phase 24 P0-1 OUTCOME Option A).

This package is the home for small helpers that read/write structured fields
on Cosmos documents at the boundary between transport-shaped doc bodies and
typed Pydantic models. The first occupant is the conversation-history
resolver used by the GA Foundry capture flow (see CONTEXT P0-1 OUTCOME).

Not to be confused with ``second_brain.db.cosmos`` (the CosmosManager / DI
container). This package is purely about field semantics on doc payloads.
"""
