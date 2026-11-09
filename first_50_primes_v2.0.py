#!/usr/bin/env python3
"""Compute the first 50 prime numbers using the Sieve of Eratosthenes.

Version 2.0 incorporates the Codex review recommendations for
first_50_primes.py while keeping the default CLI behaviour unchanged:
print the first 50 primes found by the sieve.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Iterable


def _require_non_bool_int(value: object, name: str) -> int:
    """Return value if it is a plain int (bool is rejected).

    Annotations alone do not enforce types at runtime. bool is a subclass
    of int, so it is rejected explicitly to keep the public contract clear.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, not {type(value).__name__}")
    return value


def nth_prime_upper_bound(n: int) -> int:
    """Return a safe upper bound for the n-th prime.

    Expects a positive integer n.
    - For 1 <= n <= 5 the bound is the fixed constant 15 (enough for 11).
    - For n >= 6 uses ceil(n * (ln(n) + ln(ln(n)))) plus a +10 safety
      margin so the initial sieve usually covers n primes without expansion.
    """
    n = _require_non_bool_int(n, "n")
    if n < 1:
        raise ValueError("n must be a positive integer")
    if n < 6:
        return 15
    ln_n = math.log(n)
    return math.ceil(n * (ln_n + math.log(ln_n))) + 10


def sieve_of_eratosthenes(limit: int) -> list[int]:
    """Return all primes <= limit via the Sieve of Eratosthenes.

    limit must be a plain int. For limit < 2 the result is [].
    Uses a bytearray of flags (0/1) instead of list[bool] to keep memory
    proportional to one byte per candidate.
    """
    limit = _require_non_bool_int(limit, "limit")
    if limit < 2:
        return []

    is_prime = bytearray(b"\x01") * (limit + 1)
    is_prime[0] = 0
    is_prime[1] = 0

    for p in range(2, math.isqrt(limit) + 1):
        if is_prime[p]:
            for multiple in range(p * p, limit + 1, p):
                is_prime[multiple] = 0

    return [i for i, prime in enumerate(is_prime) if prime]


def first_n_primes(n: int) -> list[int]:
    """Return the first n primes using the Sieve of Eratosthenes.

    n must be a plain int (bool rejected).
    Policy for non-positive n: return [] (documented contract; not an error).
    """
    n = _require_non_bool_int(n, "n")
    if n <= 0:
        return []

    limit = nth_prime_upper_bound(n)
    primes = sieve_of_eratosthenes(limit)

    # Recompute with a doubled limit until at least n primes are available.
    while len(primes) < n:
        limit *= 2
        primes = sieve_of_eratosthenes(limit)

    return primes[:n]


def _reference_primes_up_to(limit: int) -> list[int]:
    """Independent trial-division reference (no sieve)."""
    if limit < 2:
        return []
    primes: list[int] = []
    for candidate in range(2, limit + 1):
        root = math.isqrt(candidate)
        if all(candidate % d != 0 for d in range(2, root + 1)):
            primes.append(candidate)
    return primes


def _reference_first_n(n: int) -> list[int]:
    if n <= 0:
        return []
    # Grow a trial window until enough primes are collected.
    limit = max(15, n * 20)
    while True:
        primes = _reference_primes_up_to(limit)
        if len(primes) >= n:
            return primes[:n]
        limit *= 2


def run_self_tests() -> None:
    """Compact regression tests requested by the Codex review."""
    # sieve_of_eratosthenes: every integer limit from -10 to 1000
    for limit in range(-10, 1001):
        got = sieve_of_eratosthenes(limit)
        expected = _reference_primes_up_to(limit)
        assert got == expected, f"sieve mismatch at limit={limit}"

    # first_n_primes: every integer n from -10 to 500, plus 1000
    for n in list(range(-10, 501)) + [1000]:
        got = first_n_primes(n)
        expected = _reference_first_n(n)
        assert got == expected, f"first_n_primes mismatch at n={n}"
        if n <= 0:
            assert got == []

    # Spot-check the classic 50 and the 10_000th prime
    first_50 = first_n_primes(50)
    assert len(first_50) == 50
    assert first_50[0] == 2 and first_50[-1] == 229
    assert first_50 == _reference_first_n(50)
    assert first_n_primes(10_000)[-1] == 104_729

    # Forced expansion path: start with a tiny bound by patching this module.
    original = nth_prime_upper_bound

    def tiny_bound(n: int) -> int:
        _require_non_bool_int(n, "n")
        if n < 1:
            raise ValueError("n must be a positive integer")
        return 2

    g = globals()
    g["nth_prime_upper_bound"] = tiny_bound
    try:
        assert first_n_primes(50) == first_50
    finally:
        g["nth_prime_upper_bound"] = original

    # Type-contract checks
    for bad in (0.0, 1.0, "50", None, True, False):
        try:
            first_n_primes(bad)  # type: ignore[arg-type]
        except TypeError:
            pass
        else:
            raise AssertionError(f"expected TypeError for first_n_primes({bad!r})")

    for bad in (1.0, 2.5, "10", None, True):
        try:
            sieve_of_eratosthenes(bad)  # type: ignore[arg-type]
        except TypeError:
            pass
        else:
            raise AssertionError(f"expected TypeError for sieve({bad!r})")

    try:
        nth_prime_upper_bound(0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for nth_prime_upper_bound(0)")

    # Small documented cases
    assert first_n_primes(0) == []
    assert first_n_primes(-1) == []
    assert first_n_primes(1) == [2]
    assert first_n_primes(5) == [2, 3, 5, 7, 11]
    assert sieve_of_eratosthenes(-1) == []
    assert sieve_of_eratosthenes(0) == []
    assert sieve_of_eratosthenes(1) == []
    assert sieve_of_eratosthenes(2) == [2]

    print("All self-tests passed.", file=sys.stderr)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print the first N prime numbers using the Sieve of Eratosthenes. "
            "Default N=50 matches the original assignment."
        )
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=50,
        help="how many leading primes to print (default: 50)",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run compact regression tests and exit",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        run_self_tests()
        return 0

    count = args.count
    # argparse already parsed an int; still reject negatives-as-empty politely
    # by going through the documented API (bool cannot appear via CLI type=int).
    primes = first_n_primes(count)

    print(f"First {count} prime numbers (Sieve of Eratosthenes):")
    width = max(2, len(str(max(len(primes), 1))))
    for index, prime in enumerate(primes, start=1):
        print(f"{index:{width}d}. {prime}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
