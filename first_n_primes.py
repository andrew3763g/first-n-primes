#!/usr/bin/env python3
"""Print the first N primes using the Sieve of Eratosthenes.

Requires Python 3.8 or newer (``math.isqrt``).

``N`` is a required positive integer. The default output is the numbered
list of the first N primes. ``--nth`` prints only the N-th prime.
"""

from __future__ import annotations

import argparse
import math
import operator
import sys
from collections.abc import Iterator
from itertools import compress, islice
from typing import SupportsIndex, cast

__all__ = [
    "first_n_primes",
    "nth_prime",
    "primes_up_to",
    "sieve_of_eratosthenes",
]

# Counts above this are rejected on the command line before any sieve
# is allocated. 10 million is large enough for real use and small
# enough that an extra digit is reported as a usage error.
MAX_COUNT = 10_000_000

# Added on top of the proven estimates so a float rounding error cannot
# push the sieve limit below p_n. Callers still double the limit if a
# sieve ever comes up short; that path is a safety net, not the normal one.
_BOUND_MARGIN = 10

# Rosser's theorem starts here. p_5 = 11, so a fixed limit of 15 covers 1..5.
_ROSSER_MIN_N = 6
_SMALL_N_LIMIT = 15

# Dusart's upper bound, as used for n >= 688_383:
# p_n <= n * (ln n + ln ln n - 1 + (ln ln n - 2) / ln n).
_DUSART_MIN_N = 688_383


def _as_int(value: object, name: str) -> int:
    """Return ``value`` as a plain ``int``.

    ``operator.index`` accepts ``int`` and any other type that implements
    ``__index__`` (for example ``numpy.int64``). ``bool`` is rejected
    first: it implements ``__index__``, but ``True`` must not be treated
    as ``1``.
    """
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer, not bool")
    # SupportsIndex is the __index__ protocol. operator.index performs the
    # conversion the public contract promises, including numpy integers
    # and other non-int types that define __index__.
    if not isinstance(value, SupportsIndex):
        raise TypeError(f"{name} must be an integer, not {type(value).__name__}")
    return operator.index(value)


def _nth_prime_upper_bound(n: int) -> int:
    """Return an inclusive upper bound on the n-th prime ``p_n``.

    ``n`` must be a positive integer. This function is private: its
    ``ValueError`` for ``n < 1`` is not part of the public contract.
    ``first_n_primes`` returns ``[]`` for a non-positive count, and
    ``primes_up_to`` returns ``[]`` for a limit below 2.

    * ``1 <= n < 6``: the bound is the constant 15 (``p_5`` is 11).
    * ``n >= 6``: Rosser's theorem (1938) states that
      ``p_n < n * (ln n + ln ln n)`` for every integer n in this range.
      The bound is that expression, rounded up.
    * ``n >= 688383``: Dusart's tighter bound
      ``p_n <= n * (ln n + ln ln n - 1 + (ln ln n - 2) / ln n)``
      replaces Rosser's estimate. It is still an upper bound, so the
      sieve stays correct, and the flag array is shorter.

    The theorems assume exact real arithmetic. ``math.ceil`` plus a
    margin of 10 is there so a floating-point rounding error cannot
    drop the limit below ``p_n``.
    """
    n = _as_int(n, "n")
    if n < 1:
        raise ValueError("n must be a positive integer")
    if n < _ROSSER_MIN_N:
        return _SMALL_N_LIMIT

    ln_n = math.log(n)
    ln_ln_n = math.log(ln_n)
    if n >= _DUSART_MIN_N:
        estimate = n * (ln_n + ln_ln_n - 1.0 + (ln_ln_n - 2.0) / ln_n)
    else:
        estimate = n * (ln_n + ln_ln_n)
    return math.ceil(estimate) + _BOUND_MARGIN


def _odd_sieve_flags(limit: int) -> bytearray:
    """Flag the odd primes up to ``limit`` (``limit >= 3``).

    Only odd candidates are stored. Index ``i`` is the number
    ``2 * i + 1``: index 0 is 1, index 1 is 3, index 2 is 5. A byte of
    1 means that number is still a candidate. Even numbers are absent;
    the caller yields 2 itself. This halves the flag array and the
    crossing-off work.

    Composites are cleared with a slice assignment, which runs in C.
    For an odd prime ``p`` the first multiple that is still unmarked is
    ``p * p`` (smaller multiples were cleared by a smaller prime). The
    following odd multiples of ``p`` are exactly ``p`` indices apart:
    one index steps the value by 2, so ``p`` indices step it by ``2p``.
    """
    # Last index whose odd number is still <= limit.
    last_index = (limit - 1) // 2
    size = last_index + 1
    is_prime = bytearray(b"\x01") * size
    is_prime[0] = 0

    root = math.isqrt(limit)
    # Largest i with 2 * i + 1 <= root. Primes above the root have no
    # square inside the array, so they do not need to cross anything off.
    max_index = (root - 1) // 2
    for index in range(1, max_index + 1):
        if not is_prime[index]:
            continue
        prime = 2 * index + 1
        start = (prime * prime) // 2
        is_prime[start::prime] = bytes(len(range(start, size, prime)))
    return is_prime


def _iter_primes_upto(limit: int) -> Iterator[int]:
    """Yield the primes ``<= limit`` in increasing order.

    ``limit`` is a validated ``int``. The odd-only flag array is built
    once; ``itertools.compress`` then walks it in C and skips composites.
    """
    if limit < 2:
        return
    yield 2
    if limit < 3:
        return
    odds = range(1, limit + 1, 2)
    # flags[0] is 0, so compress drops 1 and keeps 3, 5, 7, ...
    yield from compress(odds, _odd_sieve_flags(limit))


def primes_up_to(limit: int) -> list[int]:
    """Return every prime less than or equal to ``limit``.

    ``limit`` must be an integer (``bool`` is rejected). A limit below
    2 returns ``[]``. The name describes the result; the algorithm is
    the Sieve of Eratosthenes, also available as
    ``sieve_of_eratosthenes``.
    """
    limit = _as_int(limit, "limit")
    return list(_iter_primes_upto(limit))


def sieve_of_eratosthenes(limit: int) -> list[int]:
    """Return every prime ``<= limit`` using the Sieve of Eratosthenes.

    Identical to ``primes_up_to``. This name is the algorithm; that one
    is the result.
    """
    return primes_up_to(limit)


def _next_limit(limit: int) -> int:
    """Grow a sieve limit that turned out to be short.

    A non-positive limit becomes 2, so a bad bound cannot stick at 0
    (``0 * 2`` is still 0) and spin forever.
    """
    if limit < 1:
        return 2
    return limit * 2


def first_n_primes(n: int) -> list[int]:
    """Return the first ``n`` primes as a ``list[int]``.

    ``n`` must be an integer (``bool`` is rejected). A non-positive
    ``n`` returns ``[]``. This is the documented library policy; the
    command-line interface rejects those values instead.

    The list has exactly ``n`` primes. Primes past the n-th are not
    materialised: the sieve stops after ``n`` hits via ``islice``.
    """
    n = _as_int(n, "n")
    if n <= 0:
        return []

    limit = _nth_prime_upper_bound(n)
    while True:
        primes = list(islice(_iter_primes_upto(limit), n))
        if len(primes) == n:
            return primes
        limit = _next_limit(limit)


def nth_prime(n: int) -> int:
    """Return the n-th prime (1-based) without building the full list.

    ``n`` must be a positive integer. ``n < 1`` raises ``ValueError``.
    ``bool`` and other non-integers raise ``TypeError``.

    The sieve still marks every candidate up to the bound, but the
    primes themselves are counted off the flag array. Only the n-th
    value is kept.
    """
    n = _as_int(n, "n")
    if n < 1:
        raise ValueError("n must be a positive integer")

    limit = _nth_prime_upper_bound(n)
    while True:
        # Skip n - 1 primes, then take the next one. islice does not
        # store the primes it walks past.
        try:
            return next(islice(_iter_primes_upto(limit), n - 1, None))
        except StopIteration:
            limit = _next_limit(limit)


def _positive_count(text: str) -> int:
    """Parse a CLI count. argparse turns failures into exit status 2."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid positive integer: {text!r}"
        ) from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"invalid positive integer: {value}")
    if value > MAX_COUNT:
        raise argparse.ArgumentTypeError(
            f"{value} is above the limit of {MAX_COUNT}"
        )
    return value


def _ordinal(n: int) -> str:
    """Return ``n`` with an English ordinal suffix (1st, 2nd, 11th, 21st)."""
    if 10 <= (n % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _format_numbered_primes(count: int, primes: list[int]) -> str:
    """Header plus one numbered line per prime. No trailing newline."""
    width = max(2, len(str(count)))
    lines = [f"First {count} prime numbers (Sieve of Eratosthenes):"]
    lines.extend(
        f"{index:{width}d}. {prime}"
        for index, prime in enumerate(primes, start=1)
    )
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Print the first N prime numbers using the Sieve of "
            "Eratosthenes. N is a required positive integer. "
            "The default is the full numbered list; --nth prints only "
            "the N-th prime."
        )
    )
    parser.add_argument(
        "count",
        type=_positive_count,
        help=(
            "how many leading primes to print, or which prime to print "
            f"with --nth (integer from 1 to {MAX_COUNT})"
        ),
    )
    parser.add_argument(
        "--nth",
        action="store_true",
        help="print only the N-th prime instead of the full list",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns 0 on success and 1 if memory runs out.

    Invalid arguments never return: argparse exits with status 2.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    count = cast(int, args.count)
    nth = cast(bool, args.nth)
    try:
        if nth:
            prime = nth_prime(count)
            print(f"The {_ordinal(count)} prime is {prime}.")
        else:
            print(_format_numbered_primes(count, first_n_primes(count)))
    except MemoryError:
        print(
            f"error: not enough memory to compute {count} primes",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
