# Investigations behind first-n-primes 1.2.0

This file explains why version 1.2.0 is built the way it is: what was measured, which decisions follow from the numbers, and which alternatives were tried and rejected. It is the short, public version of the review rounds that led here (Codex on the first script, then three Claude reviews of 2.0, 1.0.0, and 1.1.0).

Unless stated otherwise, timings are on Linux, Python 3.13, output to `/dev/null`, best of three runs; memory is the peak resident set of the process (`ru_maxrss` via `os.wait4`). The bare interpreter with the module imported is about 14 MB.

## 1. The sieve

### Odd-only flags with slice assignment

Three variants were compared on one sieve to `L` (Python 3.10, results checked equal):

| L | Python loop over a `bytearray` (version 2.0) | slice assignment | odd numbers only + slices |
|---|---|---|---|
| 10^5 | 8.2 ms | 1.7 ms | 1.1 ms |
| 10^6 | 85 ms | 16 ms | 9.1 ms |
| 10^7 | 884 ms | 178 ms | 91 ms |

Slice assignment moves crossing-off into C (about 5x). Storing only odd numbers halves both the array and the work (about 10x in total). The index arithmetic (`i` stands for `2i + 1`, the square of `p` is at index `p*p // 2`, consecutive odd multiples are `p` indices apart) is documented in `_odd_sieve_flags` and tested against three independent implementations.

### One reusable zero buffer

Each slice assignment needs a zero buffer of the slice's length. Allocating a fresh `bytes` object per prime peaked at 157 MB for `--nth 10000000`; one buffer sized for the widest slice (prime 3) and sliced with `memoryview` peaks at 129 MB.

### Rejected

- **Bit array (1 bit per number).** Eight times less sieve memory, but without a third-party library the bit arithmetic runs in Python rather than in C slices, so it is expected to be slower (not measured). Speed and simplicity were preferred over the last 80 MB at the cap.
- **Segmented sieve.** It reduces the sieve to O(sqrt L), but at the sizes this program allows the sieve is about 90 MB, and in Python the per-segment bookkeeping is expected to cancel the cache benefit up to roughly L = 10^8 (an estimate, not measured). It adds about 30 lines of edge cases (segment joins, a prime's square on a boundary). It would be the right base for an unbounded `iter_primes()` generator, which nobody has asked for.

## 2. The upper bound on the n-th prime

The sieve limit for "the first n primes" comes from proven upper bounds on p_n:

- `n >= 6`: p_n < n (ln n + ln ln n). This follows from Rosser and Schoenfeld (1962), who proved p_n < n (ln n + ln ln n - 0.5) for n >= 20; n = 6..19 is checked directly. Axler states the n >= 6 form. (Rosser's 1939 theorem is the *lower* bound p_n > n ln n; versions up to 1.1.0 attributed the upper bound to it in a docstring.)
- `n >= 688383`: p_n <= n (ln n + ln ln n - 1 + (ln ln n - 2) / ln n), Dusart (2010). It is tighter by 6-12 %, which is the same saving in sieve memory.
- `n < 6`: the constant 15 (p_5 = 11).

The theorems are about real numbers; the code adds `math.ceil` and a margin of 10 against float rounding. Checks:

- Rosser–Schoenfeld form, every n from 6 to 10^6: the smallest relative slack is 6.2 %. The bound over p_n is 1.118 at n = 10^3 and 1.062 at n = 10^6.
- Dusart form, every n from 688383 to 10^7 (the whole command-line range): no violation. The tightest point is the threshold itself, n = 688383, where the bound exceeds p_n by **13**, and 10 of those 13 are the margin. The margin must not be "optimised" away.
- At 10^7 the bound is 179464285 against p = 179424673.
- The widening loop (`_next_limit`) never runs for real bounds; it is a safety net and is tested by forcing a bound of 2.

## 3. Writing the list

| Approach | 10^7 lines: time / peak memory |
|---|---|
| one `print` of a joined string (1.0.0) | 6.48 s / 1274 MB |
| `writelines` of a per-line generator (1.1.0) | 9.46 s / 129 MB |
| `"".join` of batches, one `write` per batch (1.2.0) | 6.21 s / 129 MB |

One joined string holds the whole table: a list of 10^7 `int`s (about 360 MB), 10^7 line strings, and the result. Writing line by line keeps memory at the size of the sieve but sends every line through the text layer separately; the output stage alone took 8.45 s against 5.57 s in batches.

Batch size, full command at N = 10^7:

| Lines per write | Time | Peak memory |
|---|---|---|
| 4096 | 6.21 s | 130 MB |
| 16384 | 6.29 s | 132 MB |
| 65536 | 6.24 s | 141 MB |

The speed is flat from 4096 up, while each line string costs about 70 bytes of objects, so 1.2.0 uses 4096. `itertools.batched` would read better but needs Python 3.12; the minimum is 3.10.

The output of 1.2.0 is byte-for-byte identical to 1.1.0 for N = 10^6 and 10^7.

## 4. Failures and exit codes

Each case below was reproduced on the previous version before it was changed.

| Situation | 1.1.0 | 1.2.0 | Why |
|---|---|---|---|
| reader closes the pipe (`\| head -1`) | 0, quiet | 0, quiet | Not a program failure. 141 (shell convention for SIGPIPE) was rejected: with `set -o pipefail` it fails pipelines that are working as intended. |
| no stdout (`>&-`, `pythonw`) | `AttributeError`, 1 | 0, quiet | `sys.stdout` is `None`. 1.0.0 used `print`, which does nothing then; 1.1.0 switched to `sys.stdout.write` and crashed. 1.2.0 restores the old behaviour. |
| write error, e.g. full disk (`> /dev/full`) | traceback, 1 | one line, **3** | 1 was documented as "out of memory"; a new code keeps the two apart. |
| `EINVAL` on write | always "closed reader" | only on Windows | Windows reports a write to a closed pipe as `EINVAL`. Elsewhere it is a real error. |
| Ctrl+C | traceback | 130, quiet | Shell convention for SIGINT. |
| out of memory | one line, 1 | one line, 1 | Unchanged. |
| invalid arguments | 2 | 2 | argparse. |

After a failed write, stdout's descriptor is pointed at `/dev/null` (the recipe in the Python `signal` documentation), otherwise the interpreter's final flush fails again and prints "Exception ignored". The `/dev/full` test checks that stderr has exactly one line.

The sieve runs before anything is written, and only the writing is inside the `OSError` handler, so an `EINVAL` or `ENOSPC` can never be mistaken for a computation result.

## 5. Command-line parsing

- **Abbreviations off** (`allow_abbrev=False`). In 1.1.0, `--n 50` was silently taken as `--nth 50` and printed one number instead of a list. That is the exact spelling a user of the old `-n 50` would try.
- **ASCII digits only**, compared as text against the cap, so `int()` never sees a 5000-digit token (it refuses strings past 4300 digits and argparse would echo the whole token).
- **N stays required**, with no default and no `-n`/`--count`. This is the author's decision, recorded as a breaking change in the README.
- **`--version`** reads `__version__`; a test keeps it equal to `version` in `pyproject.toml`. A setuptools `dynamic` version was rejected so that the version stays visible in `pyproject.toml`.

## 6. Library limits

`_ensure_supported` rejected `n > sys.maxsize`, but the sieve for n runs to about n ln n, forty times n at the top of the range. Binary search over n found that every n from **425648847054116832** (about 4.26e17) to `sys.maxsize` passed the check and then failed inside `bytearray` with `cannot fit 'int' into an index-sized integer`. 1.2.0 checks the flag array size for every limit it is about to sieve, including widened ones, before anything is allocated. A library cap equal to the command-line `MAX_COUNT` was rejected: the library promises any n that fits in memory.

## 7. Tooling and CI

- ruff and mypy are pinned exactly in the `dev` extra (a new ruff release can reformat unchanged code and turn CI red); pytest and hypothesis use major-version ranges because the newest hypothesis no longer installs on Python 3.10.
- CI runs pytest, ruff check, ruff format --check, and mypy --strict on Ubuntu and Windows with Python 3.10–3.13, installing from `.[dev]` so the tool list exists once. A second job builds the wheel, installs it, and runs `first-n-primes`; it strips `\r` because Windows writes CRLF. Permissions are read-only; pushes run only on `main` and tags.
- The Windows-only paths (`EINVAL`, `pythonw`) are covered locally by in-process tests with a fake stdout; the Windows CI job is where they run for real.
- The `Typing :: Typed` classifier was left out: a single module cannot ship a `py.typed` marker. No license field is set because the repository has no license yet; that choice belongs to the author.

## Sources

- J. B. Rosser and L. Schoenfeld, "Approximate formulas for some functions of prime numbers", *Illinois Journal of Mathematics* 6 (1962), 64–94.
- P. Dusart, "Estimates of some functions over primes without R.H.", 2010, arXiv:1002.0442.
- C. Axler, "New estimates for the nth prime number", *Journal of Integer Sequences* 22 (2019), arXiv:1706.03651 — states both bounds above with their ranges.
- J. B. Rosser, "The n-th prime is greater than n log n", *Proceedings of the London Mathematical Society* 45 (1939) — the lower bound, for contrast.
- Python documentation, `signal` module, "Note on SIGPIPE": https://docs.python.org/3/library/signal.html#note-on-sigpipe
