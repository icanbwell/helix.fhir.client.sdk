# type: ignore
import asyncio
import logging
import os
import time
from datetime import datetime, timedelta

# from async_fhir_client import FhirClient
# from async_fhir_client_sdk import FhirClient
from logging import Logger
from typing import Any

from helix_fhir_client_sdk.fhir_client import FhirClient

from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger


class MyLogger(FhirLogger):
    def __init__(self):
        self._internal_logger: Logger = logging.getLogger("FhirPerformance")
        self._internal_logger.setLevel(logging.DEBUG)

    def info(self, param: Any) -> None:
        """
        Handle messages at INFO level
        """
        self._internal_logger.info(param)

    def error(self, param: Any) -> None:
        """
        Handle messages at error level
        """
        self._internal_logger.error(param)


class ResourceDownloader:
    def __init__(self) -> None:
        self.server_url = "https://fhir.icanbwell.com/4_0_0"
        assert os.environ.get(
            "FHIR_CLIENT_ID"
        ), "FHIR_CLIENT_ID environment variable must be set"
        assert os.environ.get(
            "FHIR_CLIENT_SECRET"
        ), "FHIR_CLIENT_SECRET environment variable must be set"
        self.auth_client_id = os.environ.get("FHIR_CLIENT_ID")
        self.auth_client_secret = os.environ.get("FHIR_CLIENT_SECRET")
        self.resource = "AuditEvent"
        assert os.environ.get(
            "FHIR_CLIENT_TAG"
        ), "FHIR_CLIENT_TAG environment variable must be set"
        self.client = os.environ.get("FHIR_CLIENT_TAG")
        self.auth_scopes = [f"user/{self.resource}.read", f"access/{self.client}.*"]
        self.page_size_for_retrieving_ids = 10000
        self.start_date = datetime.strptime("2021-12-31", "%Y-%m-%d")
        self.end_date = datetime.strptime("2022-01-01", "%Y-%m-%d")
        assert self.end_date > self.start_date
        self.concurrent_requests = 10
        self.page_size_for_retrieving_resources = 100

    async def print_hi(self, name):
        start_job = time.time()

        # Use a breakpoint in the code line below to debug your script.
        print(f"Hi, {name}")  # Press ⌘F8 to toggle the breakpoint.
        # from helix_fhir_client_sdk.fhir_client import FhirClient
        fhir_client = await self.create_fhir_client()
        resources = await fhir_client.get_resources_by_query_and_last_updated_async(
            concurrent_requests=self.concurrent_requests,
            page_size_for_retrieving_resources=self.page_size_for_retrieving_resources,
            page_size_for_retrieving_ids=self.page_size_for_retrieving_ids,
            last_updated_start_date=self.start_date,
            last_updated_end_date=self.end_date,
        )

        end_job = time.time()
        print(
            f"====== Received {len(resources)} resources in {timedelta(seconds=end_job - start_job)} ======="
        )

        # for id_ in list_of_ids:
        #     print(id_)

    async def create_fhir_client(self):
        fhir_client: FhirClient = FhirClient()
        fhir_client = fhir_client.url(self.server_url)
        fhir_client = fhir_client.client_credentials(
            self.auth_client_id, self.auth_client_secret
        )
        fhir_client = fhir_client.auth_scopes(self.auth_scopes)
        fhir_client = fhir_client.resource(self.resource)
        fhir_client = fhir_client.logger(MyLogger())
        return fhir_client


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    asyncio.run(ResourceDownloader().print_hi("PyCharm"))
