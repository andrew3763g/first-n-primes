"""Tests for first_n_primes.

The sieve variants reimplemented here are independent of the module:
trial division, the version-2.0 bytearray loop, and a full (not
odd-only) sieve that crosses off with slice assignment. Production
code has to match them.
"""

from __future__ import annotations

import errno
import math
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import first_n_primes as primes
from first_n_primes import (
    first_n_primes,
    nth_prime,
    primes_up_to,
    sieve_of_eratosthenes,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "first_n_primes.py"

# Captured format of `python first_n_primes.py 50`: header, numbers 1..50,
# primes 2..229, and the newline added by print.
EXPECTED_50 = """\
First 50 prime numbers (Sieve of Eratosthenes):
 1. 2
 2. 3
 3. 5
 4. 7
 5. 11
 6. 13
 7. 17
 8. 19
 9. 23
10. 29
11. 31
12. 37
13. 41
14. 43
15. 47
16. 53
17. 59
18. 61
19. 67
20. 71
21. 73
22. 79
23. 83
24. 89
25. 97
26. 101
27. 103
28. 107
29. 109
30. 113
31. 127
32. 131
33. 137
34. 139
35. 149
36. 151
37. 157
38. 163
39. 167
40. 173
41. 179
42. 181
43. 191
44. 193
45. 197
46. 199
47. 211
48. 223
49. 227
50. 229
"""


def reference_primes_up_to(limit: int) -> list[int]:
    """Primes <= limit by trial division. No sieve."""
    if limit < 2:
        return []
    found: list[int] = []
    for candidate in range(2, limit + 1):
        root = math.isqrt(candidate)
        if all(candidate % divisor != 0 for divisor in range(2, root + 1)):
            found.append(candidate)
    return found


def reference_first_n(n: int) -> list[int]:
    if n <= 0:
        return []
    limit = 15
    while True:
        found = reference_primes_up_to(limit)
        if len(found) >= n:
            return found[:n]
        limit *= 2


def sieve_v2_loop(limit: int) -> list[int]:
    """Version 2.0 sieve: bytearray flags, Python crossing-off loop."""
    if limit < 2:
        return []
    is_prime = bytearray(b"\x01") * (limit + 1)
    is_prime[0] = 0
    is_prime[1] = 0
    for prime in range(2, math.isqrt(limit) + 1):
        if is_prime[prime]:
            for multiple in range(prime * prime, limit + 1, prime):
                is_prime[multiple] = 0
    return [number for number, flag in enumerate(is_prime) if flag]


def sieve_full_slices(limit: int) -> list[int]:
    """Full sieve: slice assignment and itertools.compress, every integer."""
    if limit < 2:
        return []
    from itertools import compress

    is_prime = bytearray(b"\x01") * (limit + 1)
    is_prime[0] = 0
    is_prime[1] = 0
    for prime in range(2, math.isqrt(limit) + 1):
        if is_prime[prime]:
            start = prime * prime
            is_prime[start::prime] = bytes(len(range(start, limit + 1, prime)))
    return list(compress(range(limit + 1), is_prime))


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def test_import_does_not_print() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import first_n_primes"],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_public_api_hides_the_bound() -> None:
    assert primes.__all__ == [
        "first_n_primes",
        "nth_prime",
        "primes_up_to",
        "sieve_of_eratosthenes",
    ]
    assert "_nth_prime_upper_bound" not in primes.__all__


def test_variants_match_reference_on_a_dense_range() -> None:
    for limit in range(-10, 501):
        expected = reference_primes_up_to(limit)
        assert primes_up_to(limit) == expected
        assert sieve_of_eratosthenes(limit) == expected
        assert sieve_v2_loop(limit) == expected
        assert sieve_full_slices(limit) == expected


def test_variants_match_at_larger_limits() -> None:
    for limit in (1000, 1024, 2048, 5000, 7919):
        expected = reference_primes_up_to(limit)
        assert primes_up_to(limit) == expected
        assert sieve_v2_loop(limit) == expected
        assert sieve_full_slices(limit) == expected


def test_first_n_matches_reference() -> None:
    for n in list(range(-10, 301)) + [500, 1000]:
        assert first_n_primes(n) == reference_first_n(n)
        if n <= 0:
            assert first_n_primes(n) == []


def test_known_primes() -> None:
    assert first_n_primes(1) == [2]
    assert first_n_primes(5) == [2, 3, 5, 7, 11]
    assert first_n_primes(50)[-1] == 229
    assert nth_prime(1) == 2
    assert nth_prime(50) == 229
    assert nth_prime(100) == 541
    assert nth_prime(1_000) == 7_919
    assert nth_prime(10_000) == 104_729
    assert first_n_primes(10_000)[-1] == 104_729
    assert nth_prime(100_000) == 1_299_709


def test_nth_prime_matches_the_list() -> None:
    for n in (1, 2, 3, 10, 11, 12, 13, 21, 50, 100, 250):
        assert nth_prime(n) == first_n_primes(n)[-1]


def test_empty_limits() -> None:
    for limit in (-10, -1, 0, 1):
        assert primes_up_to(limit) == []
        assert sieve_of_eratosthenes(limit) == []
    assert primes_up_to(2) == [2]


def test_upper_bound_covers_the_first_10000_primes() -> None:
    found = first_n_primes(10_000)
    assert found[0] == 2
    assert found[99] == 541
    assert found[999] == 7_919
    assert found[-1] == 104_729
    for n in range(1, 10_001):
        assert primes._nth_prime_upper_bound(n) >= found[n - 1]


def test_small_bounds_are_the_fixed_constant() -> None:
    for n in range(1, 6):
        assert primes._nth_prime_upper_bound(n) == 15


def test_dusart_bound_covers_primes_through_one_million() -> None:
    """The tighter large-n bound must stay above p_n, including at the join."""
    assert nth_prime(primes._DUSART_MIN_N) <= primes._nth_prime_upper_bound(
        primes._DUSART_MIN_N
    )
    assert nth_prime(1_000_000) == 15_485_863
    ceiling = 15_485_863
    found = sieve_full_slices(ceiling)
    assert found[999_999] == 15_485_863
    # Every n in the Dusart range up to one million, against an
    # independent full sieve rather than the odd-only implementation.
    for n in range(primes._DUSART_MIN_N, 1_000_001):
        assert primes._nth_prime_upper_bound(n) >= found[n - 1]


def test_bound_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        primes._nth_prime_upper_bound(0)
    with pytest.raises(ValueError):
        primes._nth_prime_upper_bound(-3)
    with pytest.raises(ValueError):
        nth_prime(0)
    with pytest.raises(ValueError):
        nth_prime(-1)


@pytest.mark.parametrize("bad", [0.0, 1.0, 2.5, "50", None, True, False])
def test_type_contract(bad: object) -> None:
    with pytest.raises(TypeError):
        first_n_primes(bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        primes_up_to(bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        nth_prime(bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        primes._nth_prime_upper_bound(bad)  # type: ignore[arg-type]


def test_index_protocol_and_int_subclass() -> None:
    class IndexInt:
        def __init__(self, value: int) -> None:
            self._value = value

        def __index__(self) -> int:
            return self._value

    class MyInt(int):
        pass

    via_index = IndexInt(8)
    assert first_n_primes(via_index) == first_n_primes(8)  # type: ignore[arg-type]
    assert nth_prime(via_index) == nth_prime(8)  # type: ignore[arg-type]
    assert primes_up_to(via_index) == primes_up_to(8)  # type: ignore[arg-type]
    assert first_n_primes(MyInt(6)) == first_n_primes(6)


def _counting_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> list[int]:
    """Count primes pulled from the flag array. Returns the counter box."""
    pulled = [0]
    real = primes._primes_from_flags

    def counting(limit: int, flags: bytearray) -> object:
        def generator() -> object:
            for prime in real(limit, flags):
                pulled[0] += 1
                yield prime

        return generator()

    monkeypatch.setattr(primes, "_primes_from_flags", counting)
    return pulled


def test_first_n_stops_after_n_primes(monkeypatch: pytest.MonkeyPatch) -> None:
    pulled = _counting_flags(monkeypatch)
    assert first_n_primes(10)[-1] == 29
    # The bound for n=10 is well above 29, so walking every prime under
    # that bound would pull more than 10 values.
    assert pulled[0] == 10


def test_nth_does_not_call_first_n_primes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pulled = _counting_flags(monkeypatch)
    assert nth_prime(10) == 29
    assert pulled[0] == 10

    def forbidden(n: int) -> list[int]:
        raise AssertionError(f"full list was built for n={n}")

    monkeypatch.setattr(primes, "first_n_primes", forbidden)
    assert primes.main(["10", "--nth"]) == 0


def test_short_bound_is_expanded_with_monkeypatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def tiny_bound(n: int) -> int:
        if n < 1:
            raise ValueError("n must be a positive integer")
        return 2

    monkeypatch.setattr(primes, "_nth_prime_upper_bound", tiny_bound)
    assert first_n_primes(50) == reference_first_n(50)
    assert nth_prime(50) == 229


def test_cli_snapshot_of_the_first_50() -> None:
    result = run_cli("50")
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == EXPECTED_50


def test_cli_nth_flag() -> None:
    for args in (("50", "--nth"), ("--nth", "50")):
        result = run_cli(*args)
        assert result.returncode == 0
        assert result.stderr == ""
        assert result.stdout == "The 50th prime is 229.\n"


@pytest.mark.parametrize(
    ("n", "line"),
    [
        (1, "The 1st prime is 2.\n"),
        (2, "The 2nd prime is 3.\n"),
        (3, "The 3rd prime is 5.\n"),
        (11, "The 11th prime is 31.\n"),
        (12, "The 12th prime is 37.\n"),
        (13, "The 13th prime is 41.\n"),
        (21, "The 21st prime is 73.\n"),
        (22, "The 22nd prime is 79.\n"),
        (23, "The 23rd prime is 83.\n"),
    ],
)
def test_cli_ordinals(n: int, line: str) -> None:
    result = run_cli(str(n), "--nth")
    assert result.returncode == 0
    assert result.stdout == line


def test_list_mode_snapshot_capsys(capsys: pytest.CaptureFixture[str]) -> None:
    assert primes.main(["50"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == EXPECTED_50


@pytest.mark.parametrize(
    ("argument", "header", "last_line"),
    [
        ("1", "First prime number (Sieve of Eratosthenes):", " 1. 2"),
        ("2", "First 2 prime numbers (Sieve of Eratosthenes):", " 2. 3"),
    ],
)
def test_header_grammar(
    argument: str,
    header: str,
    last_line: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert primes.main([argument]) == 0
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert captured.err == ""
    assert lines[0] == header
    assert lines[-1] == last_line


def test_cli_list_mode_streams(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pulled = _counting_flags(monkeypatch)

    def forbidden(n: int) -> list[int]:
        raise AssertionError(f"full list was built for n={n}")

    monkeypatch.setattr(primes, "first_n_primes", forbidden)
    assert primes.main(["10"]) == 0
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert captured.err == ""
    assert lines[0] == "First 10 prime numbers (Sieve of Eratosthenes):"
    assert lines[-1] == "10. 29"
    assert len(lines) == 11
    # Streaming stops after the 10th prime. Materialising every prime
    # under the bound would pull more.
    assert pulled[0] == 10


def test_closed_stdout_pipe_is_silent() -> None:
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), "100000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert proc.stdout is not None
        first = proc.stdout.readline()
        proc.stdout.close()
        stderr = b"" if proc.stderr is None else proc.stderr.read()
        returncode = proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
    assert first.startswith(b"First 100000 prime numbers")
    assert returncode == 0
    assert stderr == b""


def test_einval_on_stdout_is_a_quiet_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class ClosedText:
        def write(self, data: str) -> int:
            raise OSError(errno.EINVAL, "Invalid argument")

        def writelines(self, lines: object) -> None:
            raise OSError(errno.EINVAL, "Invalid argument")

        def flush(self) -> None:
            raise OSError(errno.EINVAL, "Invalid argument")

        def fileno(self) -> int:
            raise OSError(errno.EINVAL, "Invalid argument")

    monkeypatch.setattr(sys, "stdout", ClosedText())
    assert primes.main(["5", "--nth"]) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["0"],
        ["-5"],
        ["abc"],
        ["1.5"],
        ["--nth"],
        ["--nth", "0"],
        ["-1", "--nth"],
        ["--", "-5"],
        ["--", "0"],
        [str(primes.MAX_COUNT + 1)],
    ],
)
def test_invalid_cli_exits_with_status_2(args: list[str]) -> None:
    result = run_cli(*args)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "error:" in result.stderr


def test_memory_error_has_a_clear_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def explode(limit: int) -> bytearray:
        raise MemoryError

    monkeypatch.setattr(primes, "_odd_sieve_flags", explode)
    assert primes.main(["5"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "not enough memory" in captured.err


def test_huge_inputs_raise_our_overflow() -> None:
    calls = (
        lambda: first_n_primes(10**30),
        lambda: first_n_primes(10**400),
        lambda: nth_prime(10**30),
        lambda: primes_up_to(10**30),
        lambda: primes._nth_prime_upper_bound(10**400),
    )
    for call in calls:
        with pytest.raises(OverflowError) as caught:
            call()
        message = str(caught.value)
        assert "supported maximum" in message
        assert "islice" not in message
        assert "float" not in message
    with pytest.raises(OverflowError):
        first_n_primes(sys.maxsize + 1)


@pytest.mark.parametrize(
    "token",
    ["٥", "1_000", "+5", " 7 ", "1.5", "-05"],
)
def test_cli_rejects_non_plain_digits(token: str) -> None:
    result = run_cli(token)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "error:" in result.stderr


def test_negative_error_shows_the_original_text() -> None:
    result = run_cli("--", "-05")
    assert result.returncode == 2
    assert "'-05'" in result.stderr
    assert "'-5'" not in result.stderr


def test_long_invalid_token_is_truncated() -> None:
    token = "1" * 5000
    result = run_cli(token)
    assert result.returncode == 2
    assert token not in result.stderr
    assert "1" * 40 in result.stderr
    assert len(result.stderr) < 400


def test_leading_zeros_are_plain_digits() -> None:
    result = run_cli("007", "--nth")
    assert result.returncode == 0
    assert result.stdout == "The 7th prime is 17.\n"


@settings(max_examples=40, deadline=None)
@given(st.integers(min_value=-20, max_value=800))
def test_property_limit_matches_reference_and_increases(limit: int) -> None:
    found = primes_up_to(limit)
    assert found == reference_primes_up_to(limit)
    assert found == sorted(set(found))
    previous = 1
    for prime in found:
        assert prime > previous
        previous = prime


@settings(max_examples=25, deadline=None)
@given(st.integers(min_value=-5, max_value=120))
def test_property_first_n_matches_reference(n: int) -> None:
    assert first_n_primes(n) == reference_first_n(n)


@settings(max_examples=5, deadline=None)
@given(st.integers(min_value=10_000, max_value=1_000_000))
def test_property_large_limits_match_full_sieve(limit: int) -> None:
    found = primes_up_to(limit)
    assert found == sieve_full_slices(limit)
    previous = 1
    for prime in found:
        assert prime > previous
        previous = prime
