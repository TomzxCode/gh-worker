"""Tests for retry utilities."""

import subprocess

import pytest

from gh_worker.utils.retry import RetryError, async_retry, is_transient_error, retry


class TestIsTransientError:
    """Test transient error detection."""

    def test_timeout_error_is_transient(self):
        """Test that timeout errors are considered transient."""
        error = subprocess.TimeoutExpired("cmd", 30)
        assert is_transient_error(error) is True

    def test_connection_error_is_transient(self):
        """Test that connection errors are considered transient."""
        error = ConnectionError("Connection refused")
        assert is_transient_error(error) is True

    def test_os_error_is_transient(self):
        """Test that OS errors are considered transient."""
        error = OSError("Network unreachable")
        assert is_transient_error(error) is True

    def test_rate_limit_error_is_transient(self):
        """Test that rate limit errors are considered transient."""
        error = RuntimeError("rate limit exceeded")
        assert is_transient_error(error) is True

    def test_503_error_is_transient(self):
        """Test that 503 errors are considered transient."""
        error = RuntimeError("HTTP 503 Service Unavailable")
        assert is_transient_error(error) is True

    def test_value_error_not_transient(self):
        """Test that value errors are not considered transient."""
        error = ValueError("Invalid argument")
        assert is_transient_error(error) is False


class TestRetryDecorator:
    """Test retry decorator."""

    def test_success_on_first_attempt(self):
        """Test that successful function doesn't retry."""
        call_count = 0

        @retry(max_attempts=3)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "success"

        result = succeed()

        assert result == "success"
        assert call_count == 1

    def test_success_after_retries(self):
        """Test that function succeeds after retries."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        def succeed_on_third():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = succeed_on_third()

        assert result == "success"
        assert call_count == 3

    def test_max_attempts_exhausted(self):
        """Test that max attempts are respected."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Permanent failure")

        with pytest.raises(RetryError):
            always_fail()

        assert call_count == 3

    def test_non_transient_error_not_retried(self):
        """Test that non-transient errors are not retried."""
        call_count = 0

        @retry(max_attempts=3, transient_only=True)
        def fail_with_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid argument")

        with pytest.raises(ValueError):
            fail_with_value_error()

        assert call_count == 1

    def test_retry_all_errors(self):
        """Test retrying all errors when transient_only=False."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01, transient_only=False)
        def fail_with_value_error():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary invalid argument")
            return "success"

        result = fail_with_value_error()

        assert result == "success"
        assert call_count == 3


class TestAsyncRetryDecorator:
    """Test async retry decorator."""

    @pytest.mark.asyncio
    async def test_async_success_on_first_attempt(self):
        """Test that successful async function doesn't retry."""
        call_count = 0

        @async_retry(max_attempts=3)
        async def succeed():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await succeed()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_success_after_retries(self):
        """Test that async function succeeds after retries."""
        call_count = 0

        @async_retry(max_attempts=3, initial_delay=0.01)
        async def succeed_on_third():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = await succeed_on_third()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_max_attempts_exhausted(self):
        """Test that async max attempts are respected."""
        call_count = 0

        @async_retry(max_attempts=3, initial_delay=0.01)
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Permanent failure")

        with pytest.raises(RetryError):
            await always_fail()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_non_transient_error_not_retried(self):
        """Test that non-transient errors are not retried in async."""
        call_count = 0

        @async_retry(max_attempts=3, transient_only=True)
        async def fail_with_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid argument")

        with pytest.raises(ValueError):
            await fail_with_value_error()

        assert call_count == 1
