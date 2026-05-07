# Xanad Assistant Memory Boundary

This document defines the boundary between core lifecycle behavior and optional memory behavior.

## Status

This file is normative for Phase 0 memory separation.

## Core Rule

The lifecycle engine must not depend on optional memory infrastructure to inspect, plan, apply, update, repair, or restore the package.

## Optional Memory Rule

Durable or advanced memory behavior should live outside the mandatory lifecycle core and should be modeled as an optional capability pack unless later contracts justify a smaller shared primitive.

## Separation Requirements

- Core lifecycle state belongs in machine-readable lifecycle artifacts such as policy, manifest, plan files, reports, and lockfile.
- Optional memory state must not become a hidden dependency for lifecycle correctness.
- Repo-scoped memory must remain separate from user-wide preference memory.
- Session memory must not be treated as durable install state.

## Verification Requirements

- Durable memory entries that influence meaningful decisions should be citation-backed or directly verifiable from repository state.
- Memory may improve recall, but it must not replace authoritative package truth.
- Memory state must be safe to expire, discard, or rebuild without breaking lifecycle correctness.

## Installation Rule

- A default install must work without the memory pack.
- Enabling a memory-related pack may change available features, but not the correctness of setup, update, repair, or restore.
