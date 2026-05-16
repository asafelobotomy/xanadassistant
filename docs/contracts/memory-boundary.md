# xanadAssistant Memory Boundary

This document defines the boundary between core lifecycle behavior and optional memory behavior.

## Status

This file is normative for Phase 0 memory separation.

See `docs/archive/memory-v1-contract.md` for the archived v1 scope and routing model.

## Core Rule

The lifecycle engine must not depend on optional memory infrastructure to inspect, plan, apply, update, repair, or restore the package.

## Optional Memory Rule

Durable or advanced memory behavior should live outside the mandatory lifecycle core and should be modeled as an optional capability pack unless later contracts justify a smaller shared primitive.

The current package includes a small built-in memory companion server when MCP is enabled. That built-in server is permitted as a convenience layer, but it remains non-authoritative: lifecycle correctness must not depend on its presence, contents, or initialization state.

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

- A default install must work without any optional memory pack.
- The built-in memory companion may be installed by default when MCP is enabled, but setup, update, repair, restore, inspect, and check must remain correct if that companion is absent, disabled, empty, expired, or rebuilt.
- Enabling a memory-related pack may change available features, but not the correctness of setup, update, repair, or restore.
