# Harness amendment after the first frozen attempt

The first run from frozen commit
`external-freeze-v0` stopped after 30 of 404 workflow
cells. The stop occurred at `G-PAR-02` with mypy omitted: pytest exceeded the
fixed 180-second infrastructure timeout. The runner retained 30 workflow rows
and 88 command rows. No aggregate or fate-profile analysis was run.

`G-PAR-02` changes one reference in `valid_contextj` from `pos` to `label`.
This makes `label[pos]` become `label[label]`, which raises `TypeError` when the
line is reached; it does not introduce a loop. The timeout was therefore
consistent with high-volume failure reporting. The original timeout handler did
not retain partial subprocess output, so that mechanism was treated as an
inference rather than a recorded result.

A diagnostic replay of that single stopped cell, outside the result pipeline,
kept the same mutation and test suite, disabled traceback rendering, and kept a
compact failure summary. It collected all 6,405 tests and returned a test
failure in 7.829 seconds. This diagnostic selected the reporting repair; it is
not included in the study ledger.

The amended runner applies `--tb=no -rfE` to every pytest cell. These options
remove tracebacks while retaining compact failure and error summaries; they do
not change test collection, execution, order, exit status, or the 180-second
timeout. The runner now also retains normalized partial stdout and stderr on
timeout. The source archive, mutation catalog, cell order, fate definitions, and
analysis rules are unchanged; no mutant was removed or replaced. The complete
matrix restarts from the first control under a new frozen package state.

The catalog SHA-256 before amendment was
`03fe53670fd871aa05e6c069887ae09db162a466c4fcdba767267a4e28416e3b`.
The raw first-attempt files are retained outside the release tree because the
old timeout diagnostic expanded a host-local command path. Their SHA-256 values
are:

- diagnostic JSON:
  `e3648c4d84718442289af0fe49abf0d73f7249771179f52ef13c8172372aaed8`;
- workflow ledger:
  `411eaafd6f7ab76875adaa672d2c89cce69f76c397d06e60f5908857ff51f1f8`;
- command ledger:
  `9b7519e40c05757aaa5ede0737c8998e87294f223b5ef49ecad6f21fcaac4978`.
