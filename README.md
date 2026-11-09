# first-n-primes

Print the first N prime numbers using the Sieve of Eratosthenes.

`first_n_primes.py` takes N as a required positive integer and prints the first N primes as a numbered list. `--nth` prints only the N-th prime. List mode writes the header and then each line as it goes, so the process stays about the size of the sieve. The script uses only the Python standard library.

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
```

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

`N` must be a string of ASCII digits `0-9` with nothing else around it. No sign, no underscore (`1_000`), no decimal point, no surrounding spaces, and no non-ASCII digits. Leading zeros are allowed (`007` is 7). The value must be from 1 to 10000000.

Anything else is an argparse error: a message on stderr and exit code 2. The message quotes the original text, so `-05` is reported as `-05`, and a very long token is cut to about 40 characters. A missing `N` is also exit code 2.

Exit codes:

- `0` — success. This includes a closed output pipe (`python first_n_primes.py 100000 | head -1`): the program stops without a traceback.
- `1` — the sieve could not allocate memory.
- `2` — the arguments are invalid.

## Breaking change

Version 1 printed the first 50 primes with no arguments. Version 2.0 kept that default and added `-n`/`--count`. Both are gone on purpose: `N` is an input, not a default.

```bash
python first_n_primes.py 50
```

`python first_n_primes.py` and `python first_n_primes.py -n 50` exit with code 2.

## Library

`first_n_primes`, `nth_prime`, and `primes_up_to` are importable. `first_n_primes(0)` and `primes_up_to(1)` return `[]`. A positive argument above `sys.maxsize` raises `OverflowError` with a message from this module. The command-line cap of 10000000 does not apply to those functions; a value that passes the check can still raise `MemoryError` if the sieve does not fit.

## Tests

Install the development tools, then run the suite and the checks from the repository root:

```bash
python -m pip install pytest hypothesis ruff mypy
python -m pytest
python -m ruff check
python -m ruff format --check
python -m mypy --strict first_n_primes.py tests
```

Configuration for pytest, ruff, and mypy lives in `pyproject.toml`. The minimum Python version is `requires-python` there (`>=3.10`), and ruff's `target-version` and mypy's `python_version` are 3.10 as well. GitHub Actions runs these four commands on Python 3.10 and 3.13.

## Files

- `first_n_primes.py` — the command and the functions `first_n_primes`, `nth_prime`, `primes_up_to`, and `sieve_of_eratosthenes`.
- `tests/test_primes.py` — the pytest suite.
- `pyproject.toml` — package metadata, the `first-n-primes` script, and tool settings.
- `.github/workflows/ci.yml` — the checks above on Python 3.10 and 3.13.

## Changelog

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

`first_n_primes.py` печатает первые N простых чисел решетом Эратосфена. N — обязательный аргумент из цифр ASCII от 1 до 10000000, без значения по умолчанию и без флага `-n`. Это сознательный разрыв со старыми версиями: раньше без аргументов печатались первые 50. По умолчанию список пишется потоком; флаг `--nth` печатает только N-е простое. Для одного простого заголовок в единственном числе. Нужен Python 3.10 или новее. Неверный ввод завершает программу с кодом 2, нехватка памяти — с кодом 1, закрытый канал вывода — с кодом 0 и без трассировки. Тесты: `python -m pytest`.
