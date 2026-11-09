#!/usr/bin/env python3
"""Print the first N primes using the Sieve of Eratosthenes.

Requires Python 3.10 or newer.

``N`` is a required positive integer. There is no default and no
``-n``/``--count`` option. The default output is the numbered list of
the first N primes, written as a stream. ``--nth`` prints only the N-th
prime.
"""

from __future__ import annotations

import argparse
import errno
import math
import operator
import os
import re
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

# Command-line cap. Values above this are rejected before a sieve is
# allocated. List mode streams lines, so a run at this cap is sized by
# the odd-only flag array (about 90 MB at 10**7), not by a Python list of
# every prime plus one joined string.
MAX_COUNT = 10_000_000

# How much of an invalid argv token is repeated in an error message.
_CLI_PREVIEW_CHARS = 40

# Added on top of the proven estimates so a float rounding error cannot
# push the sieve limit below p_n. Callers still widen the limit if a
# sieve ever comes up short; that path is a safety net, not the normal one.
# At n = 688_383 the margin is most of the remaining slack, so it stays.
_BOUND_MARGIN = 10

# Rosser's theorem starts here. p_5 = 11, so a fixed limit of 15 covers 1..5.
_ROSSER_MIN_N = 6
_SMALL_N_LIMIT = 15

# Dusart's upper bound, as used for n >= 688_383:
# p_n <= n * (ln n + ln ln n - 1 + (ln ln n - 2) / ln n).
_DUSART_MIN_N = 688_383

_ASCII_DIGITS = re.compile(r"[0-9]+")


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


def _ensure_supported(value: int, name: str) -> None:
    """Reject magnitudes ``islice`` and ``math.log`` cannot accept cleanly.

    ``sys.maxsize`` is the largest integer those operations treat as a
    real bound. Anything larger used to raise ``ValueError`` from
    ``islice`` or ``OverflowError`` from the float conversion, with a
    message about that internal call. Callers get this function's
    message instead.
    """
    if value > sys.maxsize:
        raise OverflowError(f"{name} is above the supported maximum of {sys.maxsize}")


def _nth_prime_upper_bound(n: int) -> int:
    """Return an inclusive upper bound on the n-th prime ``p_n``.

    ``n`` must be a positive integer at most ``sys.maxsize``. This
    function is private: its ``ValueError`` for ``n < 1`` is not part of
    the public contract. ``first_n_primes`` returns ``[]`` for a
    non-positive count, and ``primes_up_to`` returns ``[]`` for a limit
    below 2. ``n > sys.maxsize`` raises ``OverflowError``.

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
    _ensure_supported(n, "n")
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
    # One zero buffer, reused for every slice assignment. The widest
    # slice belongs to prime 3 (smallest step). A fresh bytes() object
    # of that width on every prime is a second large allocation;
    # memoryview slices share this buffer instead of copying it.
    if max_index >= 1:
        start_at_three = (3 * 3) // 2
        zero_buffer = memoryview(bytes(len(range(start_at_three, size, 3))))
    else:
        zero_buffer = memoryview(b"")
    for index in range(1, max_index + 1):
        if not is_prime[index]:
            continue
        prime = 2 * index + 1
        start = (prime * prime) // 2
        span = len(range(start, size, prime))
        is_prime[start::prime] = zero_buffer[:span]
    return is_prime


def _primes_from_flags(limit: int, flags: bytearray) -> Iterator[int]:
    """Yield primes ``<= limit`` from an odd-only flag array.

    ``flags`` is empty when ``limit < 3``. Otherwise it is the array
    produced by ``_odd_sieve_flags(limit)``: index ``i`` is ``2 * i + 1``.
    """
    if limit < 2:
        return
    yield 2
    if limit < 3:
        return
    # flags[0] is 0, so compress drops 1 and keeps 3, 5, 7, ...
    yield from compress(range(1, limit + 1, 2), flags)


def _iter_primes_upto(limit: int) -> Iterator[int]:
    """Yield the primes ``<= limit`` in increasing order.

    ``limit`` is a validated ``int`` small enough to sieve.
    ``itertools.compress`` walks the flag array in C and skips composites.
    """
    if limit < 3:
        yield from _primes_from_flags(limit, bytearray())
        return
    yield from _primes_from_flags(limit, _odd_sieve_flags(limit))


def _sieve_count(limit: int) -> tuple[int, bytearray]:
    """Return how many primes are ``<= limit``, and the odd-flag array."""
    if limit < 2:
        return 0, bytearray()
    if limit < 3:
        return 1, bytearray()
    flags = _odd_sieve_flags(limit)
    # Index 0 (the number 1) is clear, so count(1) is the odd primes.
    return 1 + flags.count(1), flags


def _covering_sieve(n: int) -> tuple[int, bytearray]:
    """Return a limit and odd-flags that contain at least ``n`` primes.

    ``n`` is a positive integer at most ``sys.maxsize``. The bound is
    widened only when a sieve comes up short.
    """
    limit = _nth_prime_upper_bound(n)
    while True:
        count, flags = _sieve_count(limit)
        if count >= n:
            return limit, flags
        limit = _next_limit(limit)


def primes_up_to(limit: int) -> list[int]:
    """Return every prime less than or equal to ``limit``.

    ``limit`` must be an integer (``bool`` is rejected). A limit below
    2 returns ``[]``. A limit above ``sys.maxsize`` raises
    ``OverflowError`` with a message from this module, before any sieve
    is allocated. The name describes the result; the algorithm is the
    Sieve of Eratosthenes, also available as ``sieve_of_eratosthenes``.
    """
    limit = _as_int(limit, "limit")
    if limit < 2:
        return []
    _ensure_supported(limit, "limit")
    return list(_iter_primes_upto(limit))


def sieve_of_eratosthenes(limit: int) -> list[int]:
    """Return every prime ``<= limit`` using the Sieve of Eratosthenes.

    Identical to ``primes_up_to``, including the ``OverflowError`` for a
    limit above ``sys.maxsize``. This name is the algorithm; that one is
    the result.
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

    ``n > sys.maxsize`` raises ``OverflowError`` (``n is above the
    supported maximum of ...``) instead of letting ``islice`` or
    ``math.log`` fail with their own text.

    The returned list has exactly ``n`` primes. Primes past the n-th
    are not stored: iteration stops after ``n`` hits via ``islice``.
    Building that list is the library contract. The command-line list
    mode streams lines and does not call this function.
    """
    n = _as_int(n, "n")
    if n <= 0:
        return []
    _ensure_supported(n, "n")
    limit, flags = _covering_sieve(n)
    return list(islice(_primes_from_flags(limit, flags), n))


def nth_prime(n: int) -> int:
    """Return the n-th prime (1-based) without building the full list.

    ``n`` must be a positive integer. ``n < 1`` raises ``ValueError``.
    ``n > sys.maxsize`` raises ``OverflowError`` with this module's
    message, not an ``islice`` or ``float`` error. ``bool`` and other
    non-integers raise ``TypeError``.

    The sieve still marks every candidate up to the bound, but the
    primes themselves are counted off the flag array. Only the n-th
    value is kept.
    """
    n = _as_int(n, "n")
    if n < 1:
        raise ValueError("n must be a positive integer")
    _ensure_supported(n, "n")
    limit, flags = _covering_sieve(n)
    # Skip n - 1 primes, then take the next one. islice does not store
    # the primes it walks past. The covering sieve has at least n primes.
    return next(islice(_primes_from_flags(limit, flags), n - 1, None))


def _preview(text: str) -> str:
    """Quote ``text`` for an error, keeping at most 40 characters of it."""
    if len(text) <= _CLI_PREVIEW_CHARS:
        return repr(text)
    return repr(f"{text[:_CLI_PREVIEW_CHARS]}...")


def _positive_count(text: str) -> int:
    """Parse a CLI count. argparse turns failures into exit status 2.

    The token must be one or more ASCII digits ``0-9`` and nothing else:
    no sign, no underscore, no decimal point, no surrounding whitespace,
    and no non-ASCII digits. Leading zeros are fine (``007`` is 7).
    The original token is what the error repeats, so ``-05`` stays
    ``-05``. Long tokens are cut to about 40 characters.
    """
    shown = _preview(text)
    if _ASCII_DIGITS.fullmatch(text) is None:
        raise argparse.ArgumentTypeError(f"invalid positive integer: {shown}")
    # Compare digits as text. int() refuses strings past a few thousand
    # digits (ValueError), and argparse would then echo the whole token.
    canonical = text.lstrip("0") or "0"
    limit_digits = str(MAX_COUNT)
    too_big = len(canonical) > len(limit_digits) or (
        len(canonical) == len(limit_digits) and canonical > limit_digits
    )
    if too_big:
        raise argparse.ArgumentTypeError(f"{shown} is above the limit of {MAX_COUNT}")
    if canonical == "0":
        raise argparse.ArgumentTypeError(f"invalid positive integer: {shown}")
    return int(canonical)


def _ordinal(n: int) -> str:
    """Return ``n`` with an English ordinal suffix (1st, 2nd, 11th, 21st)."""
    if 10 <= (n % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _list_header(count: int) -> str:
    """Singular when one prime is requested, plural otherwise."""
    if count == 1:
        return "First prime number (Sieve of Eratosthenes):"
    return f"First {count} prime numbers (Sieve of Eratosthenes):"


def _write_numbered_primes(count: int) -> None:
    """Stream the numbered list. No prime list and no joined string.

    The odd-flag array is the large object. Lines are formatted one at
    a time and handed to ``writelines``.
    """
    width = max(2, len(str(count)))
    limit, flags = _covering_sieve(count)
    primes = islice(_primes_from_flags(limit, flags), count)
    sys.stdout.write(_list_header(count) + "\n")
    sys.stdout.writelines(
        f"{index:{width}d}. {prime}\n" for index, prime in enumerate(primes, start=1)
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Print the first N prime numbers using the Sieve of "
            "Eratosthenes. N is a required positive integer written in "
            "ASCII digits. The default is the full numbered list; "
            "--nth prints only the N-th prime."
        )
    )
    parser.add_argument(
        "count",
        type=_positive_count,
        help=(
            "how many leading primes to print, or which prime to print "
            f"with --nth (ASCII digits, value from 1 to {MAX_COUNT})"
        ),
    )
    parser.add_argument(
        "--nth",
        action="store_true",
        help="print only the N-th prime instead of the full list",
    )
    return parser


def _redirect_stdout_to_devnull() -> None:
    """Point stdout at devnull so the interpreter's exit flush stays quiet.

    This is the recipe in the Python ``signal`` docs ("Note on SIGPIPE").
    A closed pipe has already raised; flushing the old stdout again
    during shutdown would raise a second time and print a traceback.
    """
    try:
        stdout_fd = sys.stdout.fileno()
    except (AttributeError, OSError, ValueError):
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, stdout_fd)
    finally:
        os.close(devnull)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Returns 0 on success. A closed stdout pipe (``BrokenPipeError``, or
    ``OSError`` with ``errno.EINVAL`` on Windows) is also success: the
    reader went away, which is not a program failure, and it must not
    be confused with running out of memory.

    Returns 1 when the sieve cannot allocate. Invalid arguments never
    return: argparse exits with status 2.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    count = cast(int, args.count)
    nth = cast(bool, args.nth)
    try:
        if nth:
            prime = nth_prime(count)
            sys.stdout.write(f"The {_ordinal(count)} prime is {prime}.\n")
        else:
            _write_numbered_primes(count)
        # Flush here so a closed pipe raises inside this block, not
        # later while the interpreter is shutting down.
        sys.stdout.flush()
    except MemoryError:
        print(
            f"error: not enough memory to compute {count} primes",
            file=sys.stderr,
        )
        return 1
    except BrokenPipeError:
        _redirect_stdout_to_devnull()
        return 0
    except OSError as exc:
        if exc.errno != errno.EINVAL:
            raise
        _redirect_stdout_to_devnull()
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
