import logging
from datetime import datetime
from typing import Optional, List

import aiohttp
import pytest
from aioresponses import aioresponses
from furl import furl

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.fhir_delete_mixin import FhirDeleteMixin
from helix_fhir_client_sdk.function_types import RefreshTokenResult
from helix_fhir_client_sdk.responses.fhir_delete_response import FhirDeleteResponse


class TestFhirDeleteMixin:
    @pytest.fixture
    def fhir_delete_mixin(self) -> FhirDeleteMixin:
        """Fixture for initializing the FhirDeleteMixin instance"""
        mixin = FhirClient()
        mixin._url = "https://example.com"
        mixin._id = "123"
        mixin._resource = "Patient"
        mixin._additional_request_headers = {}
        mixin._internal_logger = logging.getLogger("FhirClient")
        mixin._logger = None
        mixin._retry_count = 3
        mixin._exclude_status_codes_from_retry = []
        mixin._use_data_streaming = False
        mixin._internal_logger = logging.getLogger("FhirClient")

        # Mocking async methods directly
        # noinspection PyUnusedLocal
        async def mock_refresh_token_function(
            url: Optional[str],
            status_code: Optional[int],
            current_token: Optional[str],
            expiry_date: Optional[datetime],
            retry_count: Optional[int],
        ) -> RefreshTokenResult:
            return RefreshTokenResult(
                access_token=None, expiry_date=None, abort_request=False
            )

        mixin._access_token = "fake_token"
        mixin._refresh_token_function = mock_refresh_token_function

        return mixin

    @pytest.mark.asyncio
    async def test_delete_async_success(
        self, fhir_delete_mixin: FhirDeleteMixin
    ) -> None:
        """Test successful delete_async"""
        async with aiohttp.ClientSession() as session:
            with aioresponses() as m:
                fhir_delete_mixin.create_http_session = lambda: session  # type: ignore[method-assign]
                url = (
                    furl(fhir_delete_mixin._url)
                    / fhir_delete_mixin._resource
                    / fhir_delete_mixin._id
                )
                m.delete(
                    url.tostr(),
                    status=200,
                    headers={"X-Request-ID": "test-request-id"},
                    payload="{}",
                )

                response: FhirDeleteResponse = await fhir_delete_mixin.delete_async()

                assert response.status == 200
                assert response.request_id == "test-request-id"
                assert response.error is None

    @pytest.mark.asyncio
    async def test_delete_async_no_id(self, fhir_delete_mixin: FhirDeleteMixin) -> None:
        """Test delete_async raises ValueError when no ID is provided"""
        fhir_delete_mixin._id = None

        with pytest.raises(
            ValueError, match="delete requires the ID of FHIR object to delete"
        ):
            await fhir_delete_mixin.delete_async()

    @pytest.mark.asyncio
    async def test_delete_async_no_resource(
        self, fhir_delete_mixin: FhirDeleteMixin
    ) -> None:
        """Test delete_async raises ValueError when no resource is provided"""
        fhir_delete_mixin._resource = None

        with pytest.raises(ValueError, match="delete requires a FHIR resource type"):
            await fhir_delete_mixin.delete_async()

    @pytest.mark.asyncio
    async def test_delete_async_with_error(
        self, fhir_delete_mixin: FhirDeleteMixin
    ) -> None:
        """Test delete_async returns error response on non-200 status code"""
        with aioresponses() as m:
            url = (
                furl(fhir_delete_mixin._url)
                / fhir_delete_mixin._resource
                / fhir_delete_mixin._id
            )
            m.delete(
                url.tostr(),
                status=404,
                headers={"X-Request-ID": "test-request-id"},
                payload="{}",
            )

            response: FhirDeleteResponse = await fhir_delete_mixin.delete_async()

            assert response.status == 404
            assert response.error == "404"
            assert response.request_id == "test-request-id"

    @pytest.mark.asyncio
    async def test_delete_by_query_async_success(
        self, fhir_delete_mixin: FhirDeleteMixin
    ) -> None:
        """Test successful delete_by_query_async"""

        async def mock_build_url(
            *,
            additional_parameters: Optional[List[str]],
            id_above: Optional[str],
            ids: Optional[List[str]],
            page_number: Optional[int],
            resource_type: Optional[str],
        ) -> str:
            return "https://example.com/Patient?_query=example"

        fhir_delete_mixin.build_url = mock_build_url  # type: ignore[method-assign]

        with aioresponses() as m:
            url = "https://example.com/Patient?_query=example"
            m.delete(
                url,
                status=200,
                headers={"X-Request-ID": "test-request-id"},
                payload={"deleted": 1},
            )

            response: FhirDeleteResponse = (
                await fhir_delete_mixin.delete_by_query_async()
            )

            assert response.status == 200
            assert response.request_id == "test-request-id"
            assert response.count == 1
            assert response.error is None

    @pytest.mark.asyncio
    async def test_delete_by_query_async_no_resource(
        self, fhir_delete_mixin: FhirDeleteMixin
    ) -> None:
        """Test delete_by_query_async raises ValueError when no resource is provided"""
        fhir_delete_mixin._resource = None

        with pytest.raises(ValueError, match="delete requires a FHIR resource type"):
            await fhir_delete_mixin.delete_by_query_async()

    @pytest.mark.asyncio
    async def test_delete_by_query_async_with_error(
        self, fhir_delete_mixin: FhirDeleteMixin
    ) -> None:
        """Test delete_by_query_async returns error response on non-200 status code"""

        async def mock_build_url(
            *,
            additional_parameters: Optional[List[str]],
            id_above: Optional[str],
            ids: Optional[List[str]],
            page_number: Optional[int],
            resource_type: Optional[str],
        ) -> str:
            return "https://example.com/Patient?_query=example"

        fhir_delete_mixin.build_url = mock_build_url  # type: ignore[method-assign]

        async with aiohttp.ClientSession() as session:
            with aioresponses() as m:
                fhir_delete_mixin.create_http_session = lambda: session  # type: ignore[method-assign]
                url = "https://example.com/Patient?_query=example"
                m.delete(
                    url,
                    status=500,
                    headers={"X-Request-ID": "test-request-id"},
                    payload={},
                )

                fhir_delete_mixin._exclude_status_codes_from_retry = [500]
                response: FhirDeleteResponse = (
                    await fhir_delete_mixin.delete_by_query_async()
                )

                assert response.status == 500
                assert response.error == "500"
                assert response.request_id == "test-request-id"
