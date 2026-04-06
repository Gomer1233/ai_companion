# PR-003: Core Contracts + Config Layer

## Goal

Introduce stable contracts and centralized config before migrating persistence.

## In Scope

- `UserRef`
- `ConversationRef`
- conversation lifecycle rules
- reset-scope API
- `InboundEvent`
- `CoreResponse`
- `OutboundItem`
- `Settings`
- `ProviderRegistry`
- `AppVariantConfig`
- `ChannelAdapterConfig`
- deferred job contract
- minimal analytics schema

## Out of Scope

- schema migration
- repository extraction
- business-logic extraction

## Expected Files

- `src/core/contracts.py`
- `src/app/settings.py`
- `src/app/provider_registry.py`
- `src/app/variants.py`
- related tests

## Test Focus

- env parsing and validation
- provider support matrix
- ordered `CoreResponse.items`
- conversation-scoped `active mode`
- deferred job model invariants

## Merge Criteria

- contracts exist and are test-covered
- runtime config no longer depends on scattered `os.getenv()` access
- no schema migration is introduced in this PR
