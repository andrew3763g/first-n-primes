# first-n-primes

Print the first N prime numbers using the Sieve of Eratosthenes.

`first_n_primes.py` takes N as a required positive integer and prints the first N primes as a numbered list. `--nth` prints only the N-th prime. The script uses only the Python standard library.

Requires Python 3.8 or newer (`math.isqrt`).

## Run

```bash
python first_n_primes.py 50
python first_n_primes.py 100
python first_n_primes.py 50 --nth
```

List output:

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

- `N` (positional, required): how many primes to print. An integer from 1 to 10000000. With `--nth`, it is the index of the single prime to print (1 is the first prime, 2).
- `--nth`: print only the N-th prime. Omit it to print the full numbered list.

Missing, zero, negative, and non-integer values are argparse errors: a message on stderr and exit code 2. The same happens for a count above 10000000. If the process runs out of memory, the script prints a short message on stderr and exits with code 1.

## Tests

Install the development tools, then run the suite and the type checker from the repository root:

```bash
python -m pip install pytest hypothesis ruff mypy
python -m pytest
python -m ruff check
python -m mypy --strict first_n_primes.py tests
```

Configuration for pytest, ruff, and mypy lives in `pyproject.toml`. The minimum Python version is `requires-python` there, and it is repeated in the module docstring.

## Files

- `first_n_primes.py` — the command and the functions `first_n_primes`, `nth_prime`, `primes_up_to`, and `sieve_of_eratosthenes`.
- `tests/test_primes.py` — the pytest suite.
- `pyproject.toml` — Python requirement, plus pytest, ruff, and mypy settings.

## Кратко по-русски

`first_n_primes.py` печатает первые N простых чисел решетом Эратосфена. N — обязательный положительный целый аргумент от 1 до 10000000. По умолчанию печатается весь пронумерованный список; флаг `--nth` печатает только N-е простое. Нужен Python 3.8 или новее. Неверный ввод завершает программу с кодом 2. Тесты: `python -m pytest`.
