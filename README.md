# LifecycleQuorum

A standalone GenLayer Intelligent Contract that records consensus-checked lifecycle phases for Node.js major releases by independently comparing the official Node.js release schedule with the endoflife.date Node.js registry.

## Why this contract exists

Teams make runtime and deployment choices using support-status claims that change over time. LifecycleQuorum gives other contracts and tools a small, auditable on-chain answer for a Node.js major version, with the source snapshots and comparison fields that led to it. It is not a product dashboard and has no frontend or funds.

This is a bounded Node.js implementation of a reusable pattern: independently fetch two public lifecycle sources, normalize their claims, preserve disagreements rather than selecting a favorable source, and expose the resulting receipt to downstream readers.

## Why GenLayer consensus is consequential

The source documents are live web data and can change independently. The contract does not trust a caller's submitted status or a single leader's fetch. The leader fetches both fixed source URLs, parses the requested cycle, hashes both raw responses, and derives the normalized lifecycle record. Every validator independently repeats both requests and the parsing.

The custom validator requires exact equality of the complete normalized record, both raw-response hashes, and the status derived from the transaction's UTC date. For the endoflife.date `support` boundary versus Node.js `maintenance` transition only, the contract uses a documented seven-calendar-day equivalence window. All other required lifecycle fields must match exactly. The accepted record retains both dates so consumers can inspect the tolerance. Only the consensus-accepted record is appended to state.

This design intentionally uses no LLM. Both initial sources provide structured lifecycle data, so deterministic parsing and a custom validator are more appropriate than asking a model to rephrase those facts. GenLayer supplies independent web retrieval and consensus; contract code handles normalization and policy.

## Sources

1. Official Node.js Release Working Group schedule: <https://raw.githubusercontent.com/nodejs/Release/main/schedule.json>
2. endoflife.date Node.js public API: <https://endoflife.date/api/nodejs.json>

The second source is a community lifecycle registry, not an official Node.js authority. Matching fields provide corroboration, not proof that either source is infallible. If they disagree, the contract records `SOURCE_CONFLICT` and does not label the cycle supported.

## States

- `CURRENT`: released, before LTS, and before scheduled EOL.
- `ACTIVE_LTS`: at or after LTS, before maintenance, and before EOL.
- `MAINTENANCE_LTS`: at or after maintenance start and before EOL.
- `END_OF_LIFE`: on or after the scheduled end date.
- `NOT_YET_RELEASED`: the transaction date is before the scheduled start.
- `SOURCE_CONFLICT`: required lifecycle fields differ between sources.
- `UNRESOLVED`: a source, cycle, or required field cannot be interpreted safely.

These are lifecycle labels, not a guarantee that a given release is secure, patched, or suitable for a particular application.

## Methods

### Write

- `assess_cycle(major)`: permissionlessly assesses a Node.js major version, for example `24`. Appends one consensus-accepted observation. History is bounded to 20 assessments per major.

### Views

- `get_latest(major)`: latest accepted observation, or a `NO_OBSERVATION` response.
- `get_observation(major, sequence)`: a historical immutable record.
- `status_codes()`: precise status meanings.

The two URLs are fixed in the contract, not supplied per call. The only caller-controlled input is a bounded numeric major version. Transaction time is read from the GenLayer message context; it is not user-supplied.

## Verification

```bash
python -m unittest discover -s tests -v
python -m py_compile contracts/lifecycle_quorum.py
```

Local tests exercise deterministic parsing and lifecycle boundaries with synthetic responses. They do not prove live web availability, GenVM compatibility, or real validator behavior. Before deployment, run one Studio smoke test for a version where both sources agree, one known EOL version, and one deliberately mismatched fixture in local tests. Inspect both consensus finality and GenVM execution success, then read the stored observation back.

## Scope and overlap

A targeted public search found adjacent GenLayer work on release provenance and semantic policy drift, but no exact Node.js lifecycle corroboration contract in the searched results. The adjacent projects are not treated as proof of uniqueness. Public searches cannot establish global uniqueness, and this contract makes no such claim.

## Current status

The GitHub repository is <https://github.com/0xmojol/LifecycleQuorum>. The contract source has been published at `contracts/lifecycle_quorum.py`. Eight deterministic local tests passed and Python syntax compilation passed. The tests do not prove GenVM compatibility or live validator behavior.

No GenLayer deployment or Portal submission has occurred. Those steps require a successful Studio full-consensus smoke test and a user-authorized wallet transaction.
