#!/usr/bin/env python3
"""Print the first N primes using the Sieve of Eratosthenes.

Requires Python 3.10 or newer.

``N`` is a required positive integer. There is no default and no
``-n``/``--count`` option. The default output is the numbered list of
the first N primes, written as a stream. ``--nth`` prints only the N-th
prime.

Exit codes: 0 success (including a reader that closed the pipe early and
a process with no stdout), 1 out of memory, 2 invalid arguments, 3 the
output could not be written, 130 interrupted with Ctrl+C.
"""

from __future__ import annotations

import argparse
import errno
import math
import operator
import os
import re
import sys
from collections.abc import Iterator, Sequence
from itertools import chain, compress, islice
from typing import SupportsIndex, TextIO, cast

__version__ = "1.2.0"

__all__ = [
    "first_n_primes",
    "nth_prime",
    "primes_up_to",
    "sieve_of_eratosthenes",
]

# Exit codes of the command-line interface. argparse itself exits with 2.
EXIT_OK = 0
EXIT_NO_MEMORY = 1
EXIT_USAGE = 2
EXIT_WRITE_ERROR = 3
EXIT_INTERRUPTED = 130

# Command-line cap. Values above this are rejected before a sieve is
# allocated. List mode streams lines, so a run at this cap is sized by
# the odd-only flag array (about 90 MB at 10**7), not by a Python list of
# every prime plus one joined string.
MAX_COUNT = 10_000_000

# List mode joins this many formatted lines into one write. One write per
# line goes through the text layer ten million times at the cap and is
# about a third slower; one write for everything holds the whole table in
# memory. Measured at N = 10**7, 4096 lines is as fast as 65_536 and adds
# about 1 MB to the peak instead of about 12 MB.
_LINES_PER_WRITE = 4096

# How much of an invalid argv token is repeated in an error message.
_CLI_PREVIEW_CHARS = 40

# Added on top of the proven estimates so a float rounding error cannot
# push the sieve limit below p_n. Callers still widen the limit if a
# sieve ever comes up short; that path is a safety net, not the normal one.
# At n = 688_383 the margin is most of the remaining slack, so it stays.
_BOUND_MARGIN = 10

# The n(ln n + ln ln n) bound holds from here (see _nth_prime_upper_bound).
# p_5 = 11, so a fixed limit of 15 covers 1..5.
_ROSSER_MIN_N = 6
_SMALL_N_LIMIT = 15

# Dusart's upper bound (Dusart 2010, arXiv:1002.0442), for n >= 688_383:
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
    """Reject an argument above ``sys.maxsize`` with this module's message.

    Larger values would otherwise fail inside ``islice`` (``ValueError``)
    or in the float conversion of the bound (``OverflowError``), with a
    message about that internal call.
    """
    if value > sys.maxsize:
        raise OverflowError(f"{name} is above the supported maximum of {sys.maxsize}")


def _sieve_size(limit: int) -> int:
    """Length of the odd-only flag array for ``limit`` (``limit >= 3``)."""
    return (limit - 1) // 2 + 1


def _ensure_sieve_fits(limit: int, n: int) -> None:
    """Reject a sieve whose flag array cannot be indexed.

    The sieve for the n-th prime runs to about ``n * ln n``, roughly forty
    times ``n`` near the top of the range. On a 64-bit build every
    ``n`` from about 4.26e17 up to ``sys.maxsize`` passes
    ``_ensure_supported`` but needs more than ``sys.maxsize`` flags, and
    ``bytearray`` would fail with ``cannot fit 'int' into an index-sized
    integer``. This check gives this module's message instead.
    """
    if _sieve_size(limit) > sys.maxsize:
        raise OverflowError(
            f"n = {n} needs a sieve up to {limit}, above the supported maximum "
            f"sieve size of {sys.maxsize} odd numbers"
        )


def _nth_prime_upper_bound(n: int) -> int:
    """Return an inclusive upper bound on the n-th prime ``p_n``.

    ``n`` must be a positive integer at most ``sys.maxsize``. This
    function is private: its ``ValueError`` for ``n < 1`` is not part of
    the public contract. ``first_n_primes`` returns ``[]`` for a
    non-positive count, and ``primes_up_to`` returns ``[]`` for a limit
    below 2. ``n > sys.maxsize`` raises ``OverflowError``.

    * ``1 <= n < 6``: the bound is the constant 15 (``p_5`` is 11).
    * ``n >= 6``: ``p_n < n * (ln n + ln ln n)``. This follows from
      Rosser and Schoenfeld (1962), who proved
      ``p_n < n * (ln n + ln ln n - 0.5)`` for ``n >= 20``; the cases
      6..19 are checked directly (Axler 2019 states the n >= 6 form).
      Rosser's own 1939 theorem is the lower bound ``p_n > n ln n``.
      The bound is the expression, rounded up.
    * ``n >= 688383``: Dusart's tighter bound
      ``p_n <= n * (ln n + ln ln n - 1 + (ln ln n - 2) / ln n)``
      (Dusart 2010) replaces it. It is still an upper bound, so the
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
    size = _sieve_size(limit)
    is_prime = bytearray(b"\x01") * size
    is_prime[0] = 0

    root = math.isqrt(limit)
    # Largest i with 2 * i + 1 <= root. Primes above the root have no
    # square inside the array, so they do not need to cross anything off.
    max_index = (root - 1) // 2
    # One zero buffer, reused for every slice assignment. The widest
    # slice belongs to prime 3 (smallest step), so it sets the length;
    # memoryview slices of it are views, not copies.
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
    widened only when a sieve comes up short. Every limit, including a
    widened one, is checked against the largest sieve that can be
    indexed before anything is allocated.
    """
    limit = _nth_prime_upper_bound(n)
    while True:
        _ensure_sieve_fits(limit, n)
        count, flags = _sieve_count(limit)
        if count >= n:
            return limit, flags
        limit = _next_limit(limit)


def primes_up_to(limit: int) -> list[int]:
    """Return every prime less than or equal to ``limit``.

    ``limit`` must be an integer (``bool`` is rejected). A limit below
    2 returns ``[]``. A limit above ``sys.maxsize`` raises
    ``OverflowError`` with a message from this module, before any sieve
    is allocated. A smaller limit can still raise ``MemoryError`` if its
    flag array does not fit. The name describes the result; the
    algorithm is the Sieve of Eratosthenes, also available as
    ``sieve_of_eratosthenes``.
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

    ``OverflowError`` with this module's message is raised before any
    allocation when ``n`` is above ``sys.maxsize`` or when the sieve for
    ``n`` would need more flags than ``sys.maxsize`` (on 64-bit builds,
    every ``n`` from about 4.26e17). A smaller ``n`` can still raise
    ``MemoryError``.

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
    ``bool`` and other non-integers raise ``TypeError``. Arguments that
    are too large raise ``OverflowError`` exactly as in
    ``first_n_primes``.

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


# --- command line ---------------------------------------------------------


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


def _numbered_lines(count: int) -> Iterator[str]:
    """Sieve now, then return the output lines of list mode lazily.

    This is a plain function, not a generator, so the sieve (and any
    ``MemoryError``) happens here, before the first line is written. The
    returned iterator formats one line per prime as it is consumed.
    """
    limit, flags = _covering_sieve(count)
    primes = islice(_primes_from_flags(limit, flags), count)
    width = max(2, len(str(count)))
    header = (_list_header(count) + "\n",)
    body = (
        f"{index:{width}d}. {prime}\n" for index, prime in enumerate(primes, start=1)
    )
    return chain(header, body)


def _nth_lines(count: int) -> Iterator[str]:
    """Compute the N-th prime now and return its single output line."""
    prime = nth_prime(count)
    return iter((f"The {_ordinal(count)} prime is {prime}.\n",))


def _write_lines(out: TextIO, lines: Iterator[str]) -> None:
    """Write ``lines`` in batches of ``_LINES_PER_WRITE``, then flush.

    Only a batch of formatted lines is held at a time, never the table.
    The flush is inside the caller's ``try`` so a closed pipe raises
    there, not later while the interpreter shuts down.
    """
    while batch := list(islice(lines, _LINES_PER_WRITE)):
        out.write("".join(batch))
    out.flush()


def _is_closed_reader(exc: OSError) -> bool:
    """True when the reader of stdout went away.

    ``BrokenPipeError`` is the closed pipe everywhere. On Windows a write
    to a pipe whose reader exited fails with ``EINVAL`` instead; that
    errno means a closed reader only there, and only for the write.
    """
    if isinstance(exc, BrokenPipeError):
        return True
    return sys.platform == "win32" and exc.errno == errno.EINVAL


def _silence_stdout() -> None:
    """Point stdout's descriptor at devnull after a failed write.

    This is the recipe in the Python ``signal`` docs ("Note on SIGPIPE").
    Text still buffered in ``sys.stdout`` is flushed again at shutdown;
    without this, that second flush fails too and Python prints
    "Exception ignored ..." to stderr.
    """
    stream = sys.stdout
    if stream is None:
        return
    try:
        stdout_fd = stream.fileno()
    except (AttributeError, OSError, ValueError):
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, stdout_fd)
    finally:
        os.close(devnull)


def _report(message: str) -> None:
    """Print one error line on stderr, if there is a stderr to print to."""
    stream = sys.stderr
    if stream is None:
        return
    try:
        stream.write(f"error: {message}\n")
        stream.flush()
    except OSError:
        pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="first-n-primes",
        description=(
            "Print the first N prime numbers using the Sieve of "
            "Eratosthenes. N is a required positive integer written in "
            "ASCII digits. The default is the full numbered list; "
            "--nth prints only the N-th prime."
        ),
        epilog=(
            "exit codes: 0 success, 1 out of memory, 2 invalid arguments, "
            "3 output could not be written, 130 interrupted"
        ),
        # Without this, "--n 50" is taken as "--nth 50".
        allow_abbrev=False,
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
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its exit code (see the module docstring).

    Arguments are parsed first, so invalid input is exit status 2 even
    when there is no stdout. With no stdout at all (a closed descriptor,
    or ``pythonw`` on Windows) there is nowhere to print, and the run is
    a quiet success, as it was when the script used ``print``.

    The sieve runs before anything is written. Only the writing is
    guarded for ``OSError``: a closed reader is success, any other write
    failure (a full disk, for example) is exit status 3 with a one-line
    message.
    """
    args = _build_parser().parse_args(argv)
    count = cast(int, args.count)
    nth = cast(bool, args.nth)

    out = sys.stdout
    if out is None:
        return EXIT_OK

    try:
        lines = _nth_lines(count) if nth else _numbered_lines(count)
        try:
            _write_lines(out, lines)
        except OSError as exc:
            _silence_stdout()
            if _is_closed_reader(exc):
                return EXIT_OK
            _report(f"cannot write output: {exc.strerror or exc}")
            return EXIT_WRITE_ERROR
    except MemoryError:
        _report(f"not enough memory to compute {count} primes")
        return EXIT_NO_MEMORY
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
