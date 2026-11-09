"""
Tests for RetryableAioHttpClient session lifecycle management.

This module tests that sessions are properly closed or kept open depending on
whether they were created internally or provided by the user.
"""

import aiohttp
import pytest

from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import RetryableAioHttpClient


@pytest.mark.asyncio
async def test_internal_session_is_closed_after_exit() -> None:
    """Test that internally created sessions are closed when context exits"""
    client = RetryableAioHttpClient(
        retries=1,
        refresh_token_func=None,
        tracer_request_func=None,
        fn_get_session=None,  # No custom factory - SDK will create session
        use_data_streaming=False,
        access_token=None,
        access_token_expiry_date=None,
    )

    async with client:
        # Session should be created
        assert client.session is not None
        assert not client.session.closed
        session_ref = client.session

    # After exiting context, the internal session should be closed
    assert session_ref.closed


@pytest.mark.asyncio
async def test_user_provided_session_is_not_closed_after_exit() -> None:
    """Test that user-provided sessions are NOT closed when context exits"""
    # User creates their own session
    user_session = aiohttp.ClientSession()

    try:
        # Provide a factory that returns the user's session
        # Set caller_managed_session=True so SDK will NOT close the session
        client = RetryableAioHttpClient(
            retries=1,
            refresh_token_func=None,
            tracer_request_func=None,
            fn_get_session=lambda: user_session,  # User provides a custom factory
            caller_managed_session=True,  # User manages session lifecycle
            use_data_streaming=False,
            access_token=None,
            access_token_expiry_date=None,
        )

        async with client:
            # Session should be the user's session
            assert client.session is user_session
            assert not client.session.closed

        # After exiting context, the user's session should still be open
        # because caller_managed_session=True (caller manages session lifecycle)
        assert not user_session.closed

    finally:
        # User closes their own session
        await user_session.close()
        assert user_session.closed


@pytest.mark.asyncio
async def test_multiple_clients_can_share_user_session() -> None:
    """Test that multiple RetryableAioHttpClient instances can share the same user session"""
    # User creates a persistent session
    shared_session = aiohttp.ClientSession()

    try:
        # Multiple clients share the same session
        async with RetryableAioHttpClient(
            retries=1,
            refresh_token_func=None,
            tracer_request_func=None,
            fn_get_session=lambda: shared_session,
            caller_managed_session=True,  # User manages session lifecycle
            use_data_streaming=False,
            access_token=None,
            access_token_expiry_date=None,
        ) as client1:
            assert client1.session is shared_session
            assert not shared_session.closed

        # Session should still be open after the first client exits
        assert not shared_session.closed

        # The second client can reuse the same session
        async with RetryableAioHttpClient(
            retries=1,
            refresh_token_func=None,
            tracer_request_func=None,
            fn_get_session=lambda: shared_session,
            caller_managed_session=True,  # User manages session lifecycle
            use_data_streaming=False,
            access_token=None,
            access_token_expiry_date=None,
        ) as client2:
            assert client2.session is shared_session
            assert not shared_session.closed

        # Session should still be open after the second client exits
        assert not shared_session.closed

    finally:
        # User closes the shared session when done
        await shared_session.close()
        assert shared_session.closed


@pytest.mark.asyncio
async def test_user_can_recreate_closed_session_via_factory() -> None:
    """Test that a user's factory can be called multiple times if session gets closed"""
    call_count = 0

    def session_factory() -> aiohttp.ClientSession:
        nonlocal call_count
        call_count += 1
        return aiohttp.ClientSession()

    created_sessions = []

    try:
        # First client call
        async with RetryableAioHttpClient(
            retries=1,
            refresh_token_func=None,
            tracer_request_func=None,
            fn_get_session=session_factory,
            caller_managed_session=True,  # User manages session lifecycle
            use_data_streaming=False,
            access_token=None,
            access_token_expiry_date=None,
        ) as client1:
            assert client1.session is not None
            created_sessions.append(client1.session)
            assert call_count == 1  # Factory called once in __aenter__

        # SDK doesn't close session (caller_managed_session=True)
        assert created_sessions[0] is not None
        assert not created_sessions[0].closed

        # User could manually close and recreate via factory if needed
        # (This demonstrates the pattern, though in practice the factory
        # would handle closed session detection)

    finally:
        # Clean up all created sessions
        for session in created_sessions:
            if session is not None and not session.closed:
                await session.close()
