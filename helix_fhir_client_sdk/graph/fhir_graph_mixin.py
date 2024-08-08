import asyncio
from typing import Optional, AsyncGenerator, List

from helix_fhir_client_sdk.function_types import (
    HandleBatchFunction,
    HandleErrorFunction,
    HandleStreamingChunkFunction,
)
from helix_fhir_client_sdk.graph.graph_definition import GraphDefinition
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.paging_result import PagingResult
from helix_fhir_client_sdk.utilities.async_runner import AsyncRunner
from helix_fhir_client_sdk.utilities.list_chunker import ListChunker


class FhirGraphMixin(FhirClientProtocol):
    async def graph_async(
        self,
        *,
        id_: str | List[str] | None = None,
        graph_definition: GraphDefinition,
        contained: bool,
        process_in_pages: Optional[bool] = None,
        fn_handle_batch: Optional[HandleBatchFunction] = None,
        fn_handle_error: Optional[HandleErrorFunction] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
        concurrent_requests: int = 1,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Executes the $graph query on the FHIR server


        :param fn_handle_streaming_chunk:
        :type fn_handle_streaming_chunk:
        :param concurrent_requests:
        :param graph_definition: definition of a graph to execute
        :param contained: whether we should return the related resources as top level list or nest them inside their
                            parent resources in a contained property
        :param process_in_pages: whether to process in batches of size page_size
        :param fn_handle_batch: Optional function to execute on each page of data.  Note that if this is passed we don't
                                return the resources in the response anymore.  If this function returns false then we
                                stop processing any further batches.
        :param fn_handle_error: function that is called when there is an error
        :param id_: id of the resource to start the graph from.   Can be a list of ids
        :return: response containing all the resources received
        """
        assert graph_definition
        assert isinstance(graph_definition, GraphDefinition)
        assert graph_definition.start
        if contained:
            if not self._additional_parameters:
                self.additional_parameters([])
            assert self._additional_parameters is not None
            self._additional_parameters.append("contained=true")
        self.action_payload(graph_definition.to_dict())
        self.resource(graph_definition.start)
        self.action("$graph")
        id_list: list[str] = []
        if isinstance(id_, list):
            id_list = id_
        elif id_:
            id_list.append(id_)
        else:
            id_list.append("1")
        self.id_(id_list)  # this is needed because the $graph endpoint requires an id
        output_queue: asyncio.Queue[PagingResult] = asyncio.Queue()
        async with self.create_http_session() as http:
            if process_in_pages:
                async for result1 in self.get_by_query_in_pages_async(  # type: ignore[attr-defined]
                    concurrent_requests=concurrent_requests,
                    output_queue=output_queue,
                    fn_handle_error=fn_handle_error,
                    fn_handle_batch=fn_handle_batch,
                    fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                ):
                    yield result1
            else:
                result: Optional[FhirGetResponse]
                chunk_size: int = self._page_size or 1
                for chunk in ListChunker.divide_into_chunks(id_list, chunk_size):
                    async for result1 in self._get_with_session_async(  # type: ignore[attr-defined]
                        session=http,
                        fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                        additional_parameters=self._additional_parameters,
                        id_above=None,
                        page_number=self._page_number,
                        ids=chunk,
                    ):
                        yield result1

    def graph(
        self,
        *,
        graph_definition: GraphDefinition,
        contained: bool,
        process_in_batches: Optional[bool] = None,
        concurrent_requests: int = 1,
    ) -> FhirGetResponse:

        return AsyncRunner.run(
            FhirGetResponse.from_async_generator(
                self.graph_async(
                    graph_definition=graph_definition,
                    contained=contained,
                    process_in_pages=process_in_batches,
                    concurrent_requests=concurrent_requests,
                )
            )
        )
