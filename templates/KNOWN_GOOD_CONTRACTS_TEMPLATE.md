# KNOWN_GOOD_CONTRACTS.md

## PURPOSE
Record only behavior that has been proven and should not regress accidentally.

Do not use this file for guesses, plans, or history.

## CONTRACT TEMPLATE

### CONTRACT: <short name>
**Status:** PROVEN / PROVISIONAL / RETIRED  
**Scope:** <feature/system/environment>  
**Evidence:** <test/build/runtime/manual/deployment evidence>  
**Last Verified:** <date/commit>

**Contract**
- <behavior that must remain true>
- <behavior that must remain true>

**Allowed Changes**
- <what may change without violating the contract>

**Protected Boundaries**
- <what must not change silently>

## ENVIRONMENT CONTRACTS
<staging/production separation>

## DATA / DATABASE CONTRACTS
<schema, persistence, RLS, RPC, migration behavior>

## API / INTEGRATION CONTRACTS
<request/response/auth/routing/external integrations>

## UI / WORKFLOW CONTRACTS
<functionally important, evidence-backed behavior>

## DEPLOYMENT CONTRACTS
<branch/environment/build/deployment boundaries>

## RETIRED CONTRACTS
<approved replacements for previous behavior>
