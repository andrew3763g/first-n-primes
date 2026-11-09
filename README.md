# first-n-primes

Print the first N prime numbers using the Sieve of Eratosthenes.

`first_n_primes.py` takes N as a required positive integer and prints the first N primes as a numbered list. `--nth` prints only the N-th prime. List mode writes the output in batches of 4096 lines as it goes, so the process stays about the size of the sieve. The script uses only the Python standard library.

Requires Python 3.10 or newer.

## Run

```bash
python first_n_primes.py 50
python first_n_primes.py 100
python first_n_primes.py 50 --nth
```

After `pip install .` the same program is available as `first-n-primes`:

```bash
first-n-primes 5
first-n-primes 50 --nth
first-n-primes --version
```

`python -m first_n_primes 5` works too.

List output for one prime, and for more than one:

```text
First prime number (Sieve of Eratosthenes):
 1. 2
```

```text
First 50 prime numbers (Sieve of Eratosthenes):
 1. 2
 ...
50. 229
```

`--nth` output:

```text
The 50th prime is 229.
```

## Parameters

- `N` (positional, required): how many primes to print. With `--nth`, it is the index of the single prime to print (1 is the first prime, 2).
- `--nth`: print only the N-th prime. Omit it to print the full numbered list.
- `--version`: print the program name and version, then exit with code 0.
- `--help`: usage, options, and the exit codes.

Options must be spelled out in full: `--n 50` is an error, not `--nth 50`.

`N` must be a string of ASCII digits `0-9` with nothing else around it. No sign, no underscore (`1_000`), no decimal point, no surrounding spaces, and no non-ASCII digits. Leading zeros are allowed (`007` is 7). The value must be from 1 to 10000000.

Anything else is an argparse error: a message on stderr and exit code 2. The message quotes the original text, so `-05` is reported as `-05`, and a very long token is cut to about 40 characters. A missing `N` is also exit code 2.

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Success. Also when the reader closes the pipe early (`python first_n_primes.py 100000 \| head -1`) and when the process has no stdout at all (`>&-`, or `pythonw` on Windows). No traceback in either case. |
| `1` | The sieve could not allocate memory. One line on stderr. |
| `2` | The arguments are invalid (argparse). |
| `3` | The output could not be written, for example on a full disk: `error: cannot write output: No space left on device`. |
| `130` | Interrupted with Ctrl+C. No traceback. |

On Windows a write to a pipe whose reader has exited fails with `EINVAL` instead of a broken pipe; there, and only there, `EINVAL` counts as a closed reader (code 0). On other systems it is a write error (code 3).

## Breaking change

Version 1 printed the first 50 primes with no arguments. Version 2.0 kept that default and added `-n`/`--count`. Both are gone on purpose: `N` is an input, not a default.

```bash
python first_n_primes.py 50
```

`python first_n_primes.py` and `python first_n_primes.py -n 50` exit with code 2.

## Library

`first_n_primes`, `nth_prime`, and `primes_up_to` (alias `sieve_of_eratosthenes`) are importable; `first_n_primes.__version__` is the version. `first_n_primes(0)` and `primes_up_to(1)` return `[]`; `nth_prime(0)` raises `ValueError`. Non-integers and `bool` raise `TypeError`; any type with `__index__` (for example `numpy.int64`) is accepted.

`OverflowError` with a message from this module is raised before anything is allocated when an argument is above `sys.maxsize`, and also when the sieve that `n` needs would have more than `sys.maxsize` flags. The sieve for the n-th prime runs to about `n ln n`, so on a 64-bit build that second check rejects every `n` from 425648847054116832 (about 4.26e17) upward, even though such an `n` is below `sys.maxsize`. The command-line cap of 10000000 does not apply to the library; a value that passes both checks can still raise `MemoryError` if the sieve does not fit in memory.

## Performance

Measured on Linux, Python 3.13, output to `/dev/null`, best of three runs, peak resident memory of the process:

| Command | 1.1.0 | 1.2.0 |
|---|---|---|
| `first-n-primes 1000000` | 0.87 s, 25 MB | 0.58 s, 26 MB |
| `first-n-primes 1000000 --nth` | 0.21 s, 25 MB | 0.21 s, 25 MB |
| `first-n-primes 10000000` | 9.24 s, 129 MB | 6.21 s, 129 MB |
| `first-n-primes 10000000 --nth` | 2.45 s, 129 MB | 2.41 s, 129 MB |

The interpreter alone takes about 14 MB. At N = 10000000 the odd-only flag array is about 90 MB; the rest is one reusable zero buffer for crossing off and one batch of output lines. Version 1.0.0 needed 1274 MB for the same list.

## Tests

Install the development tools, then run the suite and the checks from the repository root:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check
python -m ruff format --check
python -m mypy --strict first_n_primes.py tests
```

Configuration for pytest, ruff, and mypy lives in `pyproject.toml`, and so do the versions of the tools (the `dev` extra): ruff and mypy are pinned exactly so that a new release cannot turn CI red on an unchanged commit. The minimum Python version is `requires-python` there (`>=3.10`), and ruff's `target-version` and mypy's `python_version` are 3.10 as well.

GitHub Actions runs these four commands on Ubuntu and Windows with Python 3.10, 3.11, 3.12, and 3.13. A second job builds the wheel and sdist, installs the wheel, and runs the `first-n-primes` command, on Ubuntu and Windows.

## Files

- `first_n_primes.py` — the command and the functions `first_n_primes`, `nth_prime`, `primes_up_to`, and `sieve_of_eratosthenes`.
- `tests/test_primes.py` — the pytest suite.
- `pyproject.toml` — package metadata, the `first-n-primes` script, and tool settings.
- `.github/workflows/ci.yml` — the checks and the package test above.
- `investigations.md` — why 1.2.0 is built the way it is: measurements, decisions, rejected alternatives, and sources for the prime bounds.

## Changelog

### 1.2.0

- No stdout (`>&-`, `pythonw`) is a quiet exit 0 again. 1.1.0 crashed with `AttributeError` there.
- A write error other than a closed reader (for example a full disk) prints one line and exits with the new code 3. It used to print a traceback and exit with 1, the out-of-memory code.
- `EINVAL` counts as a closed reader only on Windows.
- Ctrl+C exits with code 130 and no traceback.
- List output is written in batches of 4096 lines: about a third faster at N = 10000000, for about 1 MB more memory.
- `--version`, and the exit codes in `--help`.
- Option abbreviations are off: `--n 50` is an error instead of `--nth 50`.
- The library checks the size of the sieve, not only `n`: every `n` from about 4.26e17 to `sys.maxsize` now raises this module's `OverflowError` instead of `cannot fit 'int' into an index-sized integer`. A widened sieve is checked as well.
- `__version__`, authors, keywords, classifiers, and project URLs in the package metadata.
- The bound's docstring cites its real sources: Rosser and Schoenfeld (1962) for n >= 6 and Dusart (2010) for n >= 688383. Rosser's 1939 theorem is the lower bound.
- `investigations.md` records the measurements, decisions, and rejected alternatives behind this release.
- CI installs the tools from `.[dev]` with ruff and mypy pinned, runs on Ubuntu and Windows with Python 3.10–3.13, tests the built wheel and its console script, and runs with read-only permissions.

### 1.1.0

- Stream list output, and exit 0 with no traceback when stdout is closed early.
- Reuse one zero buffer when the sieve crosses off multiples.
- Use a singular header when N is 1.
- Keep N required. No default of 50, and no `-n`/`--count`.
- Accept only plain ASCII digits on the command line, and shorten long invalid tokens in the error.
- Reject library arguments above `sys.maxsize` with this module's own `OverflowError`.
- Require Python 3.10 or newer.
- Install the `first-n-primes` console script.
- Run pytest, ruff, ruff format, and mypy on Python 3.10 and 3.13 in GitHub Actions.

### 1.0.0

- One importable script, `first_n_primes.py`, with a required N and `--nth`.

## Кратко по-русски

`first_n_primes.py` печатает первые N простых чисел решетом Эратосфена. N — обязательный аргумент из цифр ASCII от 1 до 10000000, без значения по умолчанию и без флага `-n`. Это сознательный разрыв со старыми версиями: раньше без аргументов печатались первые 50. По умолчанию список пишется потоком; флаг `--nth` печатает только N-е простое. Для одного простого заголовок в единственном числе. Нужен Python 3.10 или новее. Коды выхода: 0 — успех, в том числе когда читатель закрыл канал или у процесса нет stdout; 1 — нехватка памяти; 2 — неверные аргументы; 3 — вывод не удалось записать (например, диск заполнен); 130 — прервано Ctrl+C. Сокращения опций не принимаются: `--n 50` — ошибка. `--version` печатает версию. Тесты: `python -m pip install -e ".[dev]"`, затем `python -m pytest`.
