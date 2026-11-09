# first-n-primes

Python scripts that print prime numbers found with the Sieve of Eratosthenes.

`first_50_primes.py` is version 1. It prints the first 50 primes. `first_50_primes_v2.0.py` is version 2.0 of the same script. Its default run still prints the first 50 primes, and it adds `-n`/`--count` and `--self-test`. The version 2.0 docstring says it incorporates the Codex review of version 1. A second review compares the two versions and lists further recommendations.

Requires Python 3.8 or newer. Version 2.0 uses `math.isqrt`. Both scripts use only the Python standard library.

The reviews are written in Russian.

## Files

- `first_50_primes.py` — version 1. Prints the first 50 primes.
- `first_50_primes_v2.0.py` — version 2.0. Default is the first 50 primes; also accepts `-n`/`--count` and `--self-test`.
- `reviews/review_codex.md` — Codex review of version 1 (Russian).
- `reviews/review_claude.md` — Claude review comparing version 1 and version 2.0, with further recommendations (Russian).

## Run

```bash
python first_50_primes_v2.0.py
python first_50_primes_v2.0.py -n 100
python first_50_primes_v2.0.py --self-test
```

Version 1, which always prints the first 50 primes:

```bash
python first_50_primes.py
```

## Кратко по-русски

Скрипты печатают простые числа решетом Эратосфена. Версия 1 выводит первые 50. Версия 2.0 по умолчанию делает то же самое и принимает `-n`/`--count` и `--self-test`. Нужен Python 3.8 или новее. Ревью в каталоге `reviews/` написаны на русском языке.
