# Frozen plan: transfer to an external package

## Question

On an independently maintained software target, does the first command unit
that rejects a source mutation identify the command whose omission changes
admission through an ordered validation chain? We report exact fixed-corpus
counts. They are neither defect-prevalence estimates nor tool rankings.

## External target and provenance

- idna 3.18 source distribution from PyPI.
- Upstream repository: <https://github.com/kjd/idna>.
- Annotated release-tag object:
  28355913c58808559ff5f2f9f43017a8c7735fad.
- Release commit: f39ea903ba49eb5a0b2c6723c9a929b41ed4a0f1.
- Source archive SHA-256:
  ffb385a7e039654cef1ab9ef32c6fafe283c0c0467bba1d9029738ce4a14a848.
- License: BSD-3-Clause. The upstream license is retained as IDNA_LICENSE.md.
- Mutation target: idna/core.py.
- Test oracle: all 6,405 tests collected by the upstream suite. No test is
  selected or edited after mutant outcomes are observed.

The archive, target, tests, project configuration, license, and aggregate
source/test tree are hash-checked. The adapter imports no validator, schema,
mutation generator, or tests from the artifact-case implementation.

The first frozen attempt ended at its infrastructure timeout before a complete
matrix existed. `AMENDMENT_2026-08-18.md` records the stopped cell, preserved
evidence hashes, diagnostic replay, and reporting-only repair. The mutation
catalog and all analysis rules remain unchanged.

## Selected command projection

The idna v3.18 workflow runs Ruff formatting, Ruff lint, strict mypy, ty, and a
multi-version pytest matrix. We select and serialize four command units:

1. Ruff format check: ruff format --check idna;
2. Ruff lint: ruff check idna tests;
3. static typing: mypy --strict --python-version 3.14 idna;
4. pytest: all upstream tests.

This is an experimental projection, not the topology or full content of
upstream CI. In particular, it omits ty and all but one cell of the Python test
matrix. Upstream runs its lint job on Python 3.14. Here the locked Ruff and mypy
versions execute under Python 3.12.10 while mypy targets 3.14 semantics; pytest
uses 3.12.10, on the 3.12 minor line included in the upstream test matrix. The
local execution platform is Windows and is recorded in the manifest; upstream
jobs run on Ubuntu, so this is not an environment replica.

The local lint and test environments are fully pinned and stored separately.
They use the exact Ruff, mypy, and pytest versions from the upstream v3.18 lock
files, but they are not copies of the complete upstream environments.
Determinism settings disable mypy caches and external pytest plugins, fix the
hash seed, enable Python UTF-8 mode, and clear inherited pytest, mypy, Ruff, and
Python path overrides. Each cell uses a fresh workspace copied from one verified
extraction. A bypass omits exactly one command unit.

When collection succeeds, pytest collects all 6,405 tests and executes the
complete suite. `--tb=no` suppresses tracebacks, while `-rfE` retains compact
failure and error summaries needed to classify a documented test rejection.
Progress, exit status, the collection count, normalized output hash, and a
bounded diagnostic excerpt remain recorded. The timeout remains 180 seconds for
every command.

## Corpus fixed before outcomes

The primary corpus contains 24 single-edit production-source mutants in five
operator families:

- four operator-layout changes;
- four rotations among already-bound function parameters;
- four type-annotation atom rotations;
- six predicate-operator replacements; and
- six scalar-boundary changes.

Layout and annotation changes provide eight surface or contract edits. Parameter
rotations, predicate replacements, and scalar changes provide 16 behavioral
edits. These quotas are design constraints, not claims about real-defect
frequencies. Primary entries have no intended stage.

Candidates are enumerated from immutable source with AST and token rules. Each
candidate has a canonical descriptor. Candidate and function order derive from
the target-source SHA-256; there is no selectable random salt. Selection is
round-robin across enclosing functions within each family. Every family must
have at least twice its quota and span at least four functions. The catalog
records each complete universe digest, candidate count, function count, quota,
and selected identifiers. No tool outcome enters enumeration or selection.

Sixteen directed calibration mutations (four per command unit) are kept apart
from the primary corpus. They test routing and classification only. They cannot
enter primary fate counts or the three reported observation checks, and they do
not alter the primary cut. Two unchanged-source controls bracket each repeat.
Mutants are never replaced because they miss an expected stage or give an
inconvenient result.

## Collection and outcomes

All 40 mutants are evaluated under the baseline ordered chain and under each of
four single-command-omission configurations. Every configuration stops at its
first controlled rejection. A control runs before and after the matrix. The
collection has two serial repeats, with a fresh workspace for every cell.

A documented Ruff, mypy, or pytest rejection is controlled. Ruff formatter exit
2 is controlled only with a parse diagnostic. Pytest exit 2 is controlled only
with a listed collection, syntax, or import diagnostic. Timeouts, launch
failures, unexpected return codes, source-resolution failures, and runner errors
are infrastructure errors and stop the run. A normalized diagnostic excerpt and
its full hash accompany every non-passing command.

For a primary first-hit set H, scoped bypass yields newly accepted C or rejected
later S, and H must equal C+S. This chain has no unguarded consumer, so exception
exposure is unavailable rather than observed to be zero. Accepted means only
that a mutant passes this serialized four-command chain; it does not mean
accepted upstream or behaviorally correct. Pooled results are accompanied by a
family-specific breakdown because the operator mix is deliberately balanced.

## Stop and reporting rules

The frozen package state must contain the plan, runner, tests, catalog, environment
locks, license, clean check, and manifest. Before any mutant runs, the runner
rebuilds the catalog from the hash-pinned source and requires byte-equivalent
structured content.

Stop as soon as a condition is observable and repair the harness before a
complete restart if a bracket control fails, a cell has an infrastructure error,
hashes or unique keys drift, a fate partition does not close, a downstream
transition is impossible, or semantic outcomes or normalized command traces
differ between repeats. Do not replace mutants after a stop.
Every failed attempt writes commit-labeled workflow and command ledgers plus a
diagnostic record; a run never overwrites those records or a completed result.

Every complete result is retained and reported. We record separately whether at
least two command units have first hits, whether any nonterminal bypass leads to
a later rejection, and whether any bypass leads to admission. These observations
do not decide inclusion or constitute a quality label. No significance test,
population-frequency claim, or cross-system equality claim is made.
