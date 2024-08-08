import asyncio
import json
import time
from asyncio import Future
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Generator, AsyncGenerator

from aiohttp import ClientSession

from helix_fhir_client_sdk.filters.last_updated_filter import LastUpdatedFilter
from helix_fhir_client_sdk.function_types import (
    HandleBatchFunction,
    HandleErrorFunction,
    HandleStreamingChunkFunction,
)
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get_result import GetResult
from helix_fhir_client_sdk.responses.paging_result import PagingResult
from helix_fhir_client_sdk.utilities.async_runner import AsyncRunner
from helix_fhir_client_sdk.utilities.list_chunker import ListChunker


class FhirCompositeQueryMixin(FhirClientProtocol):
    async def get_resources_by_query_async(
        self,
        last_updated_start_date: Optional[datetime] = None,
        last_updated_end_date: Optional[datetime] = None,
        concurrent_requests: int = 10,
        page_size_for_retrieving_resources: int = 100,
        page_size_for_retrieving_ids: int = 10000,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
        fn_handle_ids: Optional[HandleBatchFunction] = None,
        fn_handle_streaming_ids: Optional[HandleStreamingChunkFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
    ) -> List[Dict[str, Any]]:
        """
        Gets results for a query by first downloading all the ids and then retrieving resources for each id in parallel


        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: function that is called when there is an error
        :param fn_handle_streaming_ids: Optional function to execute when we get ids in streaming
        :param fn_handle_streaming_chunk: Optional function to execute when we get a chunk in streaming
        :param fn_handle_ids: Optional function to execute when we get a page of ids
        :param last_updated_start_date: finds resources updated after this datetime
        :param last_updated_end_date: find resources updated before this datetime
        :param concurrent_requests: number of concurrent requests to make to the server
        :param page_size_for_retrieving_resources: number of resources to download in one batch
        :param page_size_for_retrieving_ids:: number of ids to download in one batch
        """
        start = time.time()
        list_of_ids: List[str] = [
            id_
            async for id_ in self.get_ids_for_query_async(
                concurrent_requests=concurrent_requests,
                last_updated_end_date=last_updated_end_date,
                last_updated_start_date=last_updated_start_date,
                page_size_for_retrieving_ids=page_size_for_retrieving_ids,
                fn_handle_ids=fn_handle_ids,
                fn_handle_streaming_chunk=fn_handle_streaming_ids,
                fn_handle_error=fn_handle_error,
            )
        ]
        # now split the ids
        chunks: Generator[List[str], None, None] = ListChunker.divide_into_chunks(
            list_of_ids, page_size_for_retrieving_resources
        )
        # chunks_list = list(chunks)
        resources = []

        async def add_resources_to_list(
            resources_: List[Dict[str, Any]], page_number: Optional[int]
        ) -> bool:
            """
            adds resources to a list of resources

            :param resources_:
            :param page_number:
            :return: whether to continue
            """
            end_batch = time.time()
            for resource_ in resources_:
                resources.append(resource_)
            if self._logger:
                self._logger.info(
                    f"Received {len(resources_)} resources (total={len(resources)}/{len(list_of_ids)})"
                    f" in {timedelta(seconds=(end_batch - start))} page={page_number}"
                    f" starting with resource: {resources_[0]['id'] if len(resources_) > 0 else 'none'}"
                )

            return True

        # create a new one to reset all the properties
        fhir_client = self.clone()
        fhir_client.include_only_properties(None)
        fhir_client.id_(None)
        fhir_client.additional_parameters([])
        fhir_client._filters = []

        await fhir_client.get_resources_by_id_in_parallel_batches_async(
            concurrent_requests=concurrent_requests,
            chunks=chunks,
            fn_handle_batch=fn_handle_batch or add_resources_to_list,
            fn_handle_error=fn_handle_error or self.handle_error_wrapper(),
            fn_handle_ids=fn_handle_ids,
            fn_handle_streaming_chunk=fn_handle_streaming_chunk,
        )
        return resources

    async def get_resources_by_query_and_last_updated_async(
        self,
        *,
        last_updated_start_date: datetime,
        last_updated_end_date: datetime,
        concurrent_requests: int = 10,
        page_size_for_retrieving_resources: int = 100,
        page_size_for_retrieving_ids: int = 10000,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
        fn_handle_ids: Optional[HandleBatchFunction] = None,
        fn_handle_streaming_ids: Optional[HandleStreamingChunkFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
    ) -> List[Dict[str, Any]]:
        """
        Gets results for a query by paging through one day at a time,
            first downloading all the ids and then retrieving resources for each id in parallel


        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: Optional function that is called when there is an error
        :param fn_handle_streaming_ids: Optional function to execute when we get ids in streaming
        :param fn_handle_streaming_chunk: Optional function to execute when we get a chunk in streaming
        :param fn_handle_ids: Optional function to execute when we get a page of ids
        :param last_updated_start_date: Finds the resources updated after this datetime
        :param last_updated_end_date: find resources updated before this datetime
        :param concurrent_requests: number of concurrent requests to make to the server
        :param page_size_for_retrieving_resources: number of resources to download in one batch
        :param page_size_for_retrieving_ids:: number of ids to download in one batch
        """
        return await self.get_resources_by_query_async(
            concurrent_requests=concurrent_requests,
            last_updated_end_date=last_updated_end_date,
            last_updated_start_date=last_updated_start_date,
            page_size_for_retrieving_ids=page_size_for_retrieving_ids,
            page_size_for_retrieving_resources=page_size_for_retrieving_resources,
            fn_handle_error=fn_handle_error,
            fn_handle_batch=fn_handle_batch,
            fn_handle_ids=fn_handle_ids,
            fn_handle_streaming_ids=fn_handle_streaming_ids,
            fn_handle_streaming_chunk=fn_handle_streaming_chunk,
        )

    def get_resources_by_query(
        self,
        last_updated_start_date: Optional[datetime] = None,
        last_updated_end_date: Optional[datetime] = None,
        concurrent_requests: int = 10,
        page_size_for_retrieving_resources: int = 100,
        page_size_for_retrieving_ids: int = 10000,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
    ) -> List[Dict[str, Any]]:
        """
        Gets results for a query by first downloading all the ids and then retrieving resources for each id in parallel


        :param fn_handle_streaming_chunk:
        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: function that is called when there is an error
        :param last_updated_start_date: (Optional) get ids updated after this date
        :param last_updated_end_date: (Optional) get ids updated before this date
        :param concurrent_requests: number of concurrent requests to make to the server
        :param page_size_for_retrieving_resources: number of resources to download in one batch
        :param page_size_for_retrieving_ids:: number of ids to download in one batch
        """
        return AsyncRunner.run(
            self.get_resources_by_query_async(
                last_updated_start_date=last_updated_start_date,
                last_updated_end_date=last_updated_end_date,
                concurrent_requests=concurrent_requests,
                page_size_for_retrieving_resources=page_size_for_retrieving_resources,
                page_size_for_retrieving_ids=page_size_for_retrieving_ids,
                fn_handle_batch=fn_handle_batch,
                fn_handle_error=fn_handle_error,
                fn_handle_streaming_chunk=fn_handle_streaming_chunk,
            )
        )

    def get_resources_by_query_and_last_updated(
        self,
        last_updated_start_date: datetime,
        last_updated_end_date: datetime,
        concurrent_requests: int = 10,
        page_size_for_retrieving_resources: int = 100,
        page_size_for_retrieving_ids: int = 10000,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
    ) -> List[Dict[str, Any]]:
        """
        Gets results for a query by paging through one day at a time,
            first downloading all the ids and then retrieving resources for each id in parallel


        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: Optional function that is called when there is an error
        :param last_updated_start_date: find resources updated after this datetime
        :param last_updated_end_date: find resources updated before this datetime
        :param concurrent_requests: number of concurrent requests to make to the server
        :param page_size_for_retrieving_resources: number of resources to download in one batch
        :param page_size_for_retrieving_ids:: number of ids to download in one batch
        """
        return AsyncRunner.run(
            self.get_resources_by_query_and_last_updated_async(
                last_updated_start_date=last_updated_start_date,
                last_updated_end_date=last_updated_end_date,
                concurrent_requests=concurrent_requests,
                page_size_for_retrieving_resources=page_size_for_retrieving_resources,
                page_size_for_retrieving_ids=page_size_for_retrieving_ids,
                fn_handle_batch=fn_handle_batch,
                fn_handle_error=fn_handle_error,
            )
        )

    def get_ids_for_query(
        self,
        *,
        last_updated_start_date: Optional[datetime] = None,
        last_updated_end_date: Optional[datetime] = None,
        concurrent_requests: int = 10,
        page_size_for_retrieving_ids: int = 10000,
    ) -> List[str]:
        """
        Gets just the ids of the resources matching the query


        :param last_updated_start_date: (Optional) get ids updated after this date
        :param last_updated_end_date: (Optional) get ids updated before this date
        :param concurrent_requests:
        :param page_size_for_retrieving_ids:
        :return: list of ids
        """

        # Define an asynchronous function to consume the generator and return the values
        async def consume_generator(generator: AsyncGenerator[str, None]) -> List[str]:
            results1 = []
            async for value in generator:
                results1.append(value)
            return results1

        return AsyncRunner.run(
            consume_generator(
                self.get_ids_for_query_async(
                    last_updated_start_date=last_updated_start_date,
                    last_updated_end_date=last_updated_end_date,
                    concurrent_requests=concurrent_requests,
                    page_size_for_retrieving_ids=page_size_for_retrieving_ids,
                )
            )
        )

    # noinspection PyUnusedLocal
    async def get_ids_for_query_async(
        self,
        *,
        last_updated_start_date: Optional[datetime] = None,
        last_updated_end_date: Optional[datetime] = None,
        concurrent_requests: int = 10,
        page_size_for_retrieving_ids: int = 10000,
        fn_handle_ids: Optional[HandleBatchFunction] = None,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Gets just the ids of the resources matching the query


        :param fn_handle_error:
        :param fn_handle_batch:
        :param last_updated_start_date: (Optional) get ids updated after this date
        :param last_updated_end_date: (Optional) get ids updated before this date
        :param concurrent_requests: number of concurrent requests
        :param page_size_for_retrieving_ids:
        :param fn_handle_streaming_chunk: Optional function to execute when we get a chunk in streaming
        :param fn_handle_ids: Optional function to execute when we get a page of ids
        :return: list of ids
        """
        # get only ids first
        list_of_ids: List[str] = []
        fhir_client = self.clone()
        fhir_client = fhir_client.include_only_properties(["id"])
        fhir_client = fhir_client.page_size(page_size_for_retrieving_ids)
        output_queue: asyncio.Queue[PagingResult] = asyncio.Queue()

        async def add_to_list(
            resources_: List[Dict[str, Any]], page_number: Optional[int]
        ) -> bool:
            assert isinstance(resources_, list)
            if len(resources_) > 0:
                assert isinstance(resources_[0], dict)
            end_batch = time.time()
            assert isinstance(list_of_ids, list)
            assert isinstance(resources_, list)
            for resource_ in resources_:
                assert resource_.get("resourceType") != "Bundle"
                list_of_ids.append(resource_["id"])
            if fn_handle_ids:
                await fn_handle_ids(resources_, page_number)
            if self._logger:
                self._logger.info(
                    f"Received {len(resources_)} ids from page {page_number}"
                    f" (total={len(list_of_ids)}) in {timedelta(seconds=end_batch - start)}"
                    f" starting with id: {resources_[0]['id'] if len(resources_) > 0 else 'none'}"
                )

            return True

        # get token first
        await fhir_client.get_access_token_async()
        if last_updated_start_date is not None and last_updated_end_date is not None:
            assert last_updated_end_date >= last_updated_start_date
            greater_than = last_updated_start_date - timedelta(days=1)
            less_than = greater_than + timedelta(days=1)
            last_updated_filter = LastUpdatedFilter(
                less_than=less_than, greater_than=greater_than
            )
            fhir_client = fhir_client.filter([last_updated_filter])
            while greater_than < last_updated_end_date:
                greater_than = greater_than + timedelta(days=1)
                less_than = greater_than + timedelta(days=1)
                if self._logger:
                    self._logger.info(f"===== Processing date {greater_than} =======")
                last_updated_filter.less_than = less_than
                last_updated_filter.greater_than = greater_than
                start = time.time()
                fhir_client._last_page = None  # clean any previous setting
                response: FhirGetResponse
                async for (
                    response
                ) in fhir_client.get_by_query_in_pages_async(  # type:ignore[attr-defined]
                    concurrent_requests=concurrent_requests,
                    output_queue=output_queue,
                    fn_handle_batch=add_to_list,
                    fn_handle_error=fn_handle_error or self.handle_error_wrapper(),
                    fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                ):
                    for resource in response.get_resources():
                        if "id" in resource:
                            yield resource["id"]
                fhir_client._last_page = None  # clean any previous setting
                end = time.time()
                if self._logger:
                    self._logger.info(
                        f"Runtime processing date is {timedelta(seconds=end - start)} for {len(list_of_ids)} ids"
                    )
        else:
            start = time.time()
            fhir_client._last_page = None  # clean any previous setting
            async for (
                response
            ) in fhir_client.get_by_query_in_pages_async(  # type:ignore[attr-defined]
                concurrent_requests=concurrent_requests,
                output_queue=output_queue,
                fn_handle_batch=add_to_list,
                fn_handle_error=self.handle_error_wrapper(),
                fn_handle_streaming_chunk=fn_handle_streaming_chunk,
            ):
                for resource in response.get_resources():
                    if "id" in resource:
                        yield resource["id"]
            fhir_client._last_page = None  # clean any previous setting
            end = time.time()
            if self._logger:
                self._logger.info(
                    f"Runtime processing date is {timedelta(seconds=end - start)} for {len(list_of_ids)} ids"
                )
        if self._logger:
            self._logger.info(f"====== Received {len(list_of_ids)} ids =======")

    # noinspection PyUnusedLocal
    async def get_resources_by_id_from_queue_async(
        self,
        session: ClientSession,
        chunk: List[str],
        task_number: int,
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        fn_handle_ids: Optional[HandleBatchFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Gets resources given a queue


        :param session:
        :param chunk: list of ids to load
        :param task_number:
        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: function that is called when there is an error
        :param fn_handle_streaming_chunk: Optional function to execute when we get a chunk in streaming
        :param fn_handle_ids: Optional function to execute when we get a page of ids
        :return: list of resources
        """
        result_per_chunk: GetResult
        async for result_per_chunk in self.get_with_handler_async(
            session=session,
            page_number=0,  # this stays at 0 as we're always just loading the first page with id:above
            ids=chunk,
            fn_handle_batch=fn_handle_batch,
            fn_handle_error=fn_handle_error,
            fn_handle_streaming_chunk=fn_handle_streaming_chunk,
        ):
            if result_per_chunk:
                for result_ in result_per_chunk.resources:
                    yield result_

    async def get_resources_by_id_in_parallel_batches_async(
        self,
        concurrent_requests: int,
        chunks: Generator[List[str], None, None],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        fn_handle_ids: Optional[HandleBatchFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
    ) -> List[Dict[str, Any]]:
        """
        Given a list of ids, this function loads them in parallel batches


        :param concurrent_requests:
        :param chunks: a generator that returns a list of ids to load in one batch
        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: function that is called when there is an error
        :param fn_handle_streaming_chunk: Optional function to execute when we get a chunk in streaming
        :param fn_handle_ids: Optional function to execute when we get a page of ids
        :return: list of resources
        """
        chunk: List[str]

        # Define an asynchronous function to consume the generator and return the values
        async def consume_generator(
            generator: AsyncGenerator[dict[str, Any], None]
        ) -> List[Dict[str, Any]]:
            results1 = []
            async for value in generator:
                results1.append(value)
            return results1

        # use a semaphore to control the number of concurrent tasks
        semaphore = asyncio.Semaphore(concurrent_requests)

        async def run_task(
            session: ClientSession, task_number: int, ids: List[str]
        ) -> List[Dict[str, Any]]:
            """
            Runs a task to get resources by id from the queue

            :param session: session
            :param task_number: task number
            :param ids: ids to load

            :return: list of resources
            """
            async with semaphore:
                return await consume_generator(
                    self.get_resources_by_id_from_queue_async(
                        session=session,
                        chunk=ids,
                        task_number=task_number,
                        fn_handle_batch=fn_handle_batch,
                        fn_handle_error=fn_handle_error,
                        fn_handle_ids=fn_handle_ids,
                        fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                    )
                )

        async with self.create_http_session() as http:
            tasks = [
                run_task(session=http, task_number=task_number, ids=ids)
                for task_number, ids in enumerate(chunks)
            ]
            results = await asyncio.gather(*tasks)

            # Flatten the list of lists
            aggregated_results: List[Dict[str, Any]] = [
                item for sublist in results for item in sublist
            ]
            return aggregated_results

    def handle_error_wrapper(self) -> HandleErrorFunction:
        """
        Default handler for errors.  Can be replaced by passing in fnError to functions


        """

        async def handle_error_async(
            error: str, response: str, page_number: Optional[int], url: str
        ) -> bool:
            message = f"Error: {url} {page_number} {error}: {response}"
            if self._logger:
                self._logger.error(message)
            if self._internal_logger:
                self._internal_logger.error(message)
            return True

        return handle_error_async

    async def get_with_handler_async(
        self,
        session: Optional[ClientSession],
        page_number: Optional[int],
        ids: Optional[List[str]],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
        id_above: Optional[str] = None,
    ) -> AsyncGenerator[GetResult, None]:
        """
        gets data and calls the handlers as data is received


        :param fn_handle_streaming_chunk:
        :param session:
        :param page_number:
        :param ids: ids to retrieve
        :param fn_handle_batch: function to call when data is received
        :param fn_handle_error: function to call when there is an error
        :param id_above:
        :return: list of resources
        """
        result: Optional[FhirGetResponse] = None
        async for result1 in self._get_with_session_async(  # type:ignore[attr-defined]
            page_number=page_number,
            session=session,
            ids=ids,
            additional_parameters=None,
            id_above=id_above,
            fn_handle_streaming_chunk=fn_handle_streaming_chunk,
        ):
            result = result1

        assert result

        if result.error:
            if fn_handle_error:
                await fn_handle_error(
                    error=result.error,
                    response=result.responses,
                    page_number=page_number,
                    url=result.url,
                )
            yield GetResult(
                request_id=result.request_id,
                resources=[],
                response_headers=result.response_headers,
            )
        elif not result.error and bool(result.responses):
            result_list: List[Dict[str, Any]] = []
            if self._use_data_streaming:
                # convert ndjson to a list
                assert isinstance(result.responses, str)
                ndjson_content = result.responses
                for ndjson_line in ndjson_content.splitlines():
                    if not ndjson_line.strip():
                        continue  # ignore empty lines
                    json_line = json.loads(ndjson_line)
                    result_list.append(json_line)
            else:
                result_list = json.loads(result.responses)
                if isinstance(result_list, dict):
                    result_list = [result_list]
                assert isinstance(result_list, list)
            if fn_handle_batch:
                handle_batch_result: bool = await fn_handle_batch(
                    result_list, page_number
                )
                if handle_batch_result is False:
                    self._stop_processing = True
            yield GetResult(
                request_id=result.request_id,
                resources=result_list,
                response_headers=result.response_headers,
            )
        else:
            yield GetResult(
                request_id=result.request_id,
                resources=[],
                response_headers=result.response_headers,
            )

    async def get_page_by_query_async(
        self,
        session: Optional[ClientSession],
        start_page: int,
        increment: int,
        output_queue: asyncio.Queue[PagingResult],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
    ) -> AsyncGenerator[PagingResult, None]:
        """
        Gets the specified page for query

        :param fn_handle_streaming_chunk:
        :param session:
        :param start_page:
        :param increment:
        :param output_queue: queue to use
        :param fn_handle_batch: function to call when data is received
        :param fn_handle_error: function to call when there is an error
        :return: list of paging results
        """
        page_number: int = start_page
        server_page_number: int = page_number
        result: List[PagingResult] = []
        id_above: Optional[str] = None
        while (
            not self._last_page and not self._last_page == 0
        ) or page_number < self._last_page:
            result_for_page: GetResult
            async for result_for_page in self.get_with_handler_async(
                session=session,
                page_number=server_page_number,
                ids=None,
                fn_handle_batch=fn_handle_batch,
                fn_handle_error=fn_handle_error,
                fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                id_above=id_above,
            ):
                if result_for_page and len(result_for_page.resources) > 0:
                    paging_result = PagingResult(
                        request_id=result_for_page.request_id,
                        resources=result_for_page.resources,
                        page_number=page_number,
                        response_headers=result_for_page.response_headers,
                    )
                    await output_queue.put(paging_result)
                    # get id of last resource to use as minimum for next page
                    last_json_resource = result_for_page.resources[-1]
                    if "id" in last_json_resource:
                        # use id:above to optimize the next query
                        id_above = last_json_resource["id"]
                    server_page_number = increment - 1
                    page_number = page_number + increment
                    yield paging_result
                else:
                    with self._last_page_lock:
                        if not self._last_page or page_number < self._last_page:
                            self.last_page(page_number)
                            if self._logger:
                                self._logger.info(
                                    f"Setting last page to {self._last_page}"
                                )
                    break

    async def _get_page_by_query_tasks_async(
        self,
        concurrent_requests: int,
        output_queue: asyncio.Queue[PagingResult],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        http: ClientSession,
    ) -> AsyncGenerator[PagingResult, None]:
        """
        Returns tasks to get pages by query


        :param concurrent_requests:
        :param output_queue:
        :param fn_handle_batch: function to call when data is received
        :param fn_handle_error: function to call when there is an error
        :param http: session
        :return: task
        """
        for taskNumber in range(concurrent_requests):
            async for r in self.get_page_by_query_async(
                session=http,
                start_page=taskNumber,
                increment=concurrent_requests,
                output_queue=output_queue,
                fn_handle_batch=fn_handle_batch,
                fn_handle_error=fn_handle_error,
                fn_handle_streaming_chunk=fn_handle_streaming_chunk,
            ):
                yield r

    async def get_by_query_in_pages_async(  # type: ignore[override]
        self,
        concurrent_requests: int,
        output_queue: asyncio.Queue[PagingResult],
        fn_handle_batch: Optional[HandleBatchFunction],
        fn_handle_error: Optional[HandleErrorFunction],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Retrieves the data in batches (using paging) to reduce load on the FHIR server and to reduce network traffic


        :param fn_handle_streaming_chunk:
        :param output_queue:
        :type output_queue:
        :param fn_handle_error:
        :param concurrent_requests:
        :param fn_handle_batch: function to call for each batch.  Receives a list of resources where each
                                    resource is a dictionary. If this is specified then we don't return
                                    the resources anymore.  If this function returns False then we stop
                                    processing batches
        :return response containing all the resources received
        """
        # if paging is requested then iterate through the pages until the response is empty
        assert self._url
        assert self._page_size
        self.page_number(0)
        self._stop_processing = False
        resources_list: List[Dict[str, Any]] = []

        # Define an asynchronous function to consume the generator and return the values
        async def consume_generator(
            generator: AsyncGenerator[PagingResult, None]
        ) -> List[PagingResult]:
            results = []
            async for value in generator:
                results.append(value)
            return results

        async with self.create_http_session() as http:
            first_completed: Future[List[PagingResult]]
            for first_completed in asyncio.as_completed(
                [
                    consume_generator(
                        self._get_page_by_query_tasks_async(
                            http=http,
                            output_queue=output_queue,
                            concurrent_requests=concurrent_requests,
                            fn_handle_batch=fn_handle_batch,
                            fn_handle_error=fn_handle_error,
                            fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                        )
                    )
                ]
            ):
                result_list: List[PagingResult] = await first_completed
                for resources in [r.resources for r in result_list]:
                    resources_list.extend(resources)

            yield FhirGetResponse(
                request_id=result_list[0].request_id if len(result_list) > 0 else None,
                url=self._url,
                responses=json.dumps(resources_list),
                error=None,
                access_token=self._access_token,
                total_count=len(resources_list),
                status=200,
                extra_context_to_return=self._extra_context_to_return,
                resource_type=self._resource,
                id_=self._id,
                response_headers=(
                    result_list[0].response_headers if len(result_list) > 0 else None
                ),
            )
