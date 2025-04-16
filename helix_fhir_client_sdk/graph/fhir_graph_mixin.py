from collections.abc import AsyncGenerator

from helix_fhir_client_sdk.function_types import (
    HandleStreamingChunkFunction,
)
from helix_fhir_client_sdk.graph.graph_definition import GraphDefinition
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.async_runner import AsyncRunner
from helix_fhir_client_sdk.utilities.list_chunker import ListChunker


class FhirGraphMixin(FhirClientProtocol):
    async def graph_async(
        self,
        *,
        id_: str | list[str] | None = None,
        graph_definition: GraphDefinition,
        contained: bool,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None = None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Executes the $graph query on the FHIR server


        :param fn_handle_streaming_chunk:
        :type fn_handle_streaming_chunk:
        :param graph_definition: definition of a graph to execute
        :param contained: whether we should return the related resources as top level list or nest them inside their
                            parent resources in a contained property
        :param id_: id of the resource to start the graph from.   Can be a list of ids
        :type id_: str | List[str] | None
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
        result1: FhirGetResponse | None
        chunk_size: int = self._page_size or 1
        for chunk in ListChunker.divide_into_chunks(id_list, chunk_size):
            async for result1 in self._get_with_session_async(
                fn_handle_streaming_chunk=fn_handle_streaming_chunk,
                additional_parameters=self._additional_parameters,
                id_above=None,
                page_number=self._page_number,
                ids=chunk,
                resource_type=self._resource,
            ):
                yield result1

    def graph(
        self,
        *,
        graph_definition: GraphDefinition,
        contained: bool,
    ) -> FhirGetResponse | None:
        return AsyncRunner.run(
            FhirGetResponse.from_async_generator(
                self.graph_async(
                    graph_definition=graph_definition,
                    contained=contained,
                )
            )
        )
