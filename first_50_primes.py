#!/usr/bin/env python3
"""Compute the first 50 prime numbers using the Sieve of Eratosthenes."""

from __future__ import annotations

import math


def nth_prime_upper_bound(n: int) -> int:
    """Return a safe upper bound for the n-th prime (n >= 6)."""
    if n < 6:
        return 15
    ln_n = math.log(n)
    return math.ceil(n * (ln_n + math.log(ln_n))) + 10


def sieve_of_eratosthenes(limit: int) -> list[int]:
    """Return all primes <= limit via the Sieve of Eratosthenes."""
    if limit < 2:
        return []

    is_prime = [True] * (limit + 1)
    is_prime[0] = False
    is_prime[1] = False

    for p in range(2, int(math.sqrt(limit)) + 1):
        if is_prime[p]:
            for multiple in range(p * p, limit + 1, p):
                is_prime[multiple] = False

    return [i for i, prime in enumerate(is_prime) if prime]


def first_n_primes(n: int) -> list[int]:
    """Return the first n primes using the Sieve of Eratosthenes."""
    if n <= 0:
        return []

    limit = nth_prime_upper_bound(n)
    primes = sieve_of_eratosthenes(limit)

    # Expand the sieve if the bound was somehow insufficient.
    while len(primes) < n:
        limit *= 2
        primes = sieve_of_eratosthenes(limit)

    return primes[:n]


def main() -> None:
    count = 50
    primes = first_n_primes(count)

    print(f"First {count} prime numbers (Sieve of Eratosthenes):")
    for index, prime in enumerate(primes, start=1):
        print(f"{index:2d}. {prime}")


if __name__ == "__main__":
    main()
