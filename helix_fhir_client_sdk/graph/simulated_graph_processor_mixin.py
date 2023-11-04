import asyncio
import json
from abc import abstractmethod, ABC
from datetime import datetime
from typing import Union, List, Dict, Any, Optional, cast, Tuple

from aiohttp import ClientSession

from helix_fhir_client_sdk.dictionary_parser import DictionaryParser
from helix_fhir_client_sdk.fhir_bundle import BundleEntry, Bundle
from helix_fhir_client_sdk.fhir_bundle_appender import FhirBundleAppender
from helix_fhir_client_sdk.function_types import HandleStreamingChunkFunction
from helix_fhir_client_sdk.graph.graph_definition import (
    GraphDefinition,
    GraphDefinitionLink,
    GraphDefinitionTarget,
)
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.paging_result import PagingResult
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder
from helix_fhir_client_sdk.utilities.fhir_scope_parser import FhirScopeParser
from helix_fhir_client_sdk.utilities.request_cache import RequestCache


class SimulatedGraphProcessorMixin(ABC):
    # noinspection PyPep8Naming,PyUnusedLocal
    async def process_simulate_graph_async(
        self,
        *,
        id_: Union[List[str], str],
        graph_json: Dict[str, Any],
        contained: bool,
        concurrent_requests: int = 1,
        separate_bundle_resources: bool = False,
        restrict_to_scope: Optional[str] = None,
        restrict_to_resources: Optional[List[str]] = None,
        restrict_to_capability_statement: Optional[str] = None,
        retrieve_and_restrict_to_capability_statement: Optional[bool] = None,
        ifModifiedSince: Optional[datetime] = None,
        eTag: Optional[str] = None,
        logger: Optional[FhirLogger],
        url: Optional[str],
        expand_fhir_bundle: Optional[bool],
        auth_scopes: Optional[List[str]],
    ) -> FhirGetResponse:
        """
        Simulates the $graph query on the FHIR server


        :param separate_bundle_resources:
        :param id_: single id or list of ids (ids can be comma separated too)
        :param concurrent_requests:
        :param graph_json: definition of a graph to execute
        :param contained: whether we should return the related resources as top level list or nest them inside their
                            parent resources in a contained property
        :param restrict_to_scope: Optional scope to restrict to
        :param restrict_to_resources: Optional list of resources to restrict to
        :param restrict_to_capability_statement: Optional capability statement to restrict to
        :param retrieve_and_restrict_to_capability_statement: Optional capability statement to retrieve and restrict to
        :param ifModifiedSince: Optional datetime to use for If-Modified-Since header
        :param eTag: Optional ETag to use for If-None-Match header
        :param logger: Optional logger to use
        :param url: Optional url to use
        :param expand_fhir_bundle: Optional flag to expand the FHIR bundle
        :param auth_scopes: Optional list of scopes to use
        :return: FhirGetResponse
        """
        assert graph_json
        graph_definition: GraphDefinition = GraphDefinition.from_dict(graph_json)
        assert isinstance(graph_definition, GraphDefinition)
        assert graph_definition.start

        # parse the scopes
        scope_parser: FhirScopeParser = FhirScopeParser(scopes=auth_scopes)

        # we handle separate resources differently below
        self.separate_bundle_resources(False)

        if logger:
            logger.info(
                f"FhirClient.simulate_graph_async() id_=${id_}, contained={contained}, "
                + f"separate_bundle_resources={separate_bundle_resources}"
            )

        if not isinstance(id_, list):
            id_ = id_.split(",")

        cache: RequestCache
        with RequestCache() as cache:
            output_queue: asyncio.Queue[PagingResult] = asyncio.Queue()
            async with self.create_http_session() as session:
                # first load the start resource
                start: str = graph_definition.start
                response: FhirGetResponse
                cache_hits: int
                response, cache_hits = await self._get_resources_by_parameters_async(
                    session=session,
                    resource_type=start,
                    id_=id_,
                    cache=cache,
                    scope_parser=scope_parser,
                    logger=logger,
                )
                if not response.responses:
                    return response
                parent_bundle_entries: List[BundleEntry] = response.get_bundle_entries()

                if logger:
                    logger.info(
                        f"FhirClient.simulate_graph_async() got parent resources: {len(response.get_resources())} "
                        + f"cached:{cache_hits}"
                    )
                # turn into a bundle if not already a bundle
                bundle = Bundle(entry=parent_bundle_entries)

                # now process the graph links
                responses: List[FhirGetResponse] = []
                if graph_definition.link and len(graph_definition.link) > 0:
                    link: GraphDefinitionLink
                    for link in graph_definition.link:
                        parent_bundle_entry: BundleEntry
                        for parent_bundle_entry in parent_bundle_entries:
                            responses.extend(
                                await self._process_link_async(
                                    session=session,
                                    link=link,
                                    parent_bundle_entry=parent_bundle_entry,
                                    logger=logger,
                                    cache=cache,
                                    scope_parser=scope_parser,
                                )
                            )
                FhirBundleAppender.append_responses(responses=responses, bundle=bundle)

                bundle = FhirBundleAppender.remove_duplicate_resources(bundle=bundle)

                # token, url, service_slug
                if separate_bundle_resources:
                    resources: Dict[str, Union[str, List[Dict[str, Any]]]] = {}
                    if bundle.entry:
                        entry: BundleEntry
                        for entry in bundle.entry:
                            resource: Optional[Dict[str, Any]] = entry.resource
                            if resource:
                                resource_type = resource.get("resourceType")
                                assert (
                                    resource_type
                                ), f"No resourceType in {json.dumps(resource)}"
                                if resource_type not in resources:
                                    resources[resource_type] = []
                                if isinstance(resources[resource_type], list):
                                    resources[resource_type].append(resource)  # type: ignore
                    response.responses = json.dumps(resources, cls=FhirJSONEncoder)
                elif expand_fhir_bundle:
                    if bundle.entry:
                        response.responses = json.dumps(
                            [e.resource for e in bundle.entry], cls=FhirJSONEncoder
                        )
                    else:
                        response.responses = ""
                else:
                    bundle_dict: Dict[str, Any] = bundle.to_dict()
                    response.responses = json.dumps(bundle_dict, cls=FhirJSONEncoder)

                response.url = url or response.url  # set url to top level url
                if logger:
                    logger.info(
                        f"Request Cache hits: {cache.cache_hits}, misses: {cache.cache_misses}"
                    )
                return response

    async def _process_link_async(
        self,
        *,
        session: ClientSession,
        link: GraphDefinitionLink,
        parent_bundle_entry: Optional[BundleEntry],
        logger: Optional[FhirLogger],
        cache: RequestCache,
        scope_parser: FhirScopeParser,
    ) -> List[FhirGetResponse]:
        """
        Process a GraphDefinition link object


        :param session: aiohttp session
        :param link: link to process
        :param parent_bundle_entry: parent bundle entry
        :param logger: logger to use
        :param cache: cache to use
        :param scope_parser: scope parser to use
        :return: list of FhirGetResponse objects
        """
        assert session
        assert link
        responses: List[FhirGetResponse] = []
        targets: List[GraphDefinitionTarget] = link.target
        target: GraphDefinitionTarget
        for target in targets:
            responses.extend(
                await self._process_target_async(
                    session=session,
                    target=target,
                    path=link.path,
                    parent_bundle_entry=parent_bundle_entry,
                    logger=logger,
                    cache=cache,
                    scope_parser=scope_parser,
                )
            )
        return responses

    async def _process_target_async(
        self,
        *,
        session: ClientSession,
        target: GraphDefinitionTarget,
        path: Optional[str],
        parent_bundle_entry: Optional[BundleEntry],
        logger: Optional[FhirLogger],
        cache: RequestCache,
        scope_parser: FhirScopeParser,
    ) -> List[FhirGetResponse]:
        """
        Process a GraphDefinition target


        :param session: aiohttp session
        :param target: target to process
        :param path: path to process
        :param parent_bundle_entry: parent bundle entry
        :param logger: logger to use
        :param cache: cache to use
        :param scope_parser: scope parser to use
        :return: list of FhirGetResponse objects
        """
        responses: List[FhirGetResponse] = []
        children: List[BundleEntry] = []
        child_response: FhirGetResponse
        child_response_resources: Union[Dict[str, Any], List[Dict[str, Any]]]
        target_type: Optional[str] = target.type_
        parent_resource: Optional[Dict[str, Any]] = (
            parent_bundle_entry.resource if parent_bundle_entry else None
        )
        if path:  # forward link
            if path.endswith("[x]"):  # a list
                path = path.replace("[x]", "")
                # find references
                references: Union[List[Dict[str, Any]], Dict[str, Any], str, None] = (
                    DictionaryParser.get_nested_property(parent_resource, path)
                    if parent_resource and path
                    else None
                )
                # remove null references
                if references and isinstance(references, list):
                    references = [r for r in references if r is not None]
                # iterate through all references
                if parent_resource and references and target_type:
                    reference_ids: List[str] = [
                        cast(str, r.get("reference"))
                        for r in references
                        if "reference" in r and isinstance(r, dict)
                    ]
                    for reference_id in reference_ids:
                        reference_parts = reference_id.split("/")
                        if reference_parts[0] == target_type:
                            child_id = reference_parts[1]
                            (
                                child_response,
                                cache_hits,
                            ) = await self._get_resources_by_parameters_async(
                                session=session,
                                resource_type=target_type,
                                id_=child_id,
                                cache=cache,
                                scope_parser=scope_parser,
                                logger=logger,
                            )
                            responses.append(child_response)
                            children = child_response.get_bundle_entries()
                            if logger:
                                logger.info(
                                    f"Received child resources"
                                    + f" from parent {parent_resource.get('resourceType')}/{parent_resource.get('id')}"
                                    + f" [{path}]"
                                    + f", count:{len(child_response.get_resource_type_and_ids())}, cached:{cache_hits}"
                                    + f", {','.join(child_response.get_resource_type_and_ids())}"
                                )
            else:  # single reference
                if parent_resource and parent_resource.get(path) and target_type:
                    reference = parent_resource.get(path)
                    if reference and "reference" in reference:
                        reference_id = reference["reference"]
                        reference_parts = reference_id.split("/")
                        if reference_parts[0] == target_type:
                            child_id = reference_parts[1]
                            (
                                child_response,
                                cache_hits,
                            ) = await self._get_resources_by_parameters_async(
                                session=session,
                                resource_type=target_type,
                                id_=child_id,
                                cache=cache,
                                scope_parser=scope_parser,
                                logger=logger,
                            )
                            responses.append(child_response)
                            children = child_response.get_bundle_entries()
                            if logger:
                                logger.info(
                                    f"Received child resources"
                                    + f" from parent {parent_resource.get('resourceType')}/{parent_resource.get('id')}"
                                    + f" [{path}]"
                                    + f", count:{len(child_response.get_resource_type_and_ids())}, cached:{cache_hits}"
                                    + f", {','.join(child_response.get_resource_type_and_ids())}"
                                )
        elif target.params:  # reverse path
            # for a reverse link, get the ids of the current resource, put in a view and
            # add a stage to get that
            param_list: List[str] = target.params.split("&")
            ref_param = [p for p in param_list if p.endswith("{ref}")][0]
            additional_parameters = [p for p in param_list if not p.endswith("{ref}")]
            property_name: str = ref_param.split("=")[0]
            if (
                parent_resource
                and property_name
                and parent_resource.get("id")
                and target_type
            ):
                parent_id = parent_resource.get("id")
                request_parameters: List[str] = [
                    f"{property_name}={parent_id}"
                ] + additional_parameters
                (
                    child_response,
                    cache_hits,
                ) = await self._get_resources_by_parameters_async(
                    session=session,
                    resource_type=target_type,
                    parameters=request_parameters,
                    cache=cache,
                    scope_parser=scope_parser,
                    logger=logger,
                )
                responses.append(child_response)
                if logger:
                    logger.debug(
                        f"Received child resources with params:{target.params} "
                        + f" from parent {parent_resource.get('resourceType')}/{parent_resource.get('id')}"
                        + f" [{'&'.join(request_parameters)}]"
                        + f", count:{len(child_response.get_resource_type_and_ids())}, cached:{cache_hits}"
                        + f", {','.join(child_response.get_resource_type_and_ids())}"
                    )
                children = child_response.get_bundle_entries()

        if target.link:
            child_link: GraphDefinitionLink
            for child_link in target.link:
                child: BundleEntry
                for child in children:
                    responses.extend(
                        await self._process_link_async(
                            session=session,
                            link=child_link,
                            parent_bundle_entry=child,
                            logger=logger,
                            cache=cache,
                            scope_parser=scope_parser,
                        )
                    )
        return responses

    async def _get_resources_by_parameters_async(
        self,
        *,
        id_: Optional[Union[List[str], str]] = None,
        session: ClientSession,
        resource_type: str,
        parameters: Optional[List[str]] = None,
        cache: RequestCache,
        scope_parser: FhirScopeParser,
        logger: Optional[FhirLogger],
    ) -> Tuple[FhirGetResponse, int]:
        assert session
        assert resource_type

        if not scope_parser.scope_allows(resource_type=resource_type):
            if logger:
                logger.debug(f"Skipping resource {resource_type} due to scope")
            return (
                FhirGetResponse(
                    request_id=None,
                    url="",
                    id_=None,
                    resource_type=resource_type,
                    responses="",
                    response_headers=None,
                    status=200,
                    access_token=None,
                    next_url=None,
                    total_count=0,
                    extra_context_to_return=None,
                    error=None,
                ),
                0,
            )

        self.resource(resource=resource_type)

        id_list: Optional[List[str]]
        if id_ and not isinstance(id_, list):
            id_list = [id_]
        else:
            id_list = cast(Optional[List[str]], id_)

        non_cached_id_list: List[str] = []
        # get any cached resources
        cached_bundle_entries: List[BundleEntry] = []
        cached_response: Optional[FhirGetResponse] = None
        cache_hits: int = 0
        if id_list:
            for resource_id in id_list:
                cached_bundle_entry: Optional[BundleEntry] = cache.get(
                    resource_type=resource_type, resource_id=resource_id
                )
                if cached_bundle_entry:
                    cached_bundle_entries.append(cached_bundle_entry)
                    cache_hits += 1
                else:
                    non_cached_id_list.append(resource_id)

        if cached_bundle_entries and len(cached_bundle_entries) > 0:
            if logger:
                logger.debug(f"Returning resource {resource_type} from cache")
            cached_bundle: Bundle = Bundle(entry=cached_bundle_entries)
            cached_response = FhirGetResponse(
                request_id=None,
                url=cached_bundle_entries[0].request.url
                if cached_bundle_entries[0].request
                else "",
                id_=None,
                resource_type=resource_type,
                responses=json.dumps(cached_bundle.to_dict(), cls=FhirJSONEncoder),
                response_headers=None,
                status=200,
                access_token=None,
                next_url=None,
                total_count=len(cached_bundle_entries),
                extra_context_to_return=None,
                error=None,
            )

        result: Optional[FhirGetResponse] = None
        # either we have non-cached ids or this is a query without id but has other parameters
        if len(non_cached_id_list) > 0 or not id_:
            result = await self._get_with_session_async(
                session=session,
                ids=non_cached_id_list,
                additional_parameters=parameters,
            )
            non_cached_bundle_entry: BundleEntry
            for non_cached_bundle_entry in result.get_bundle_entries():
                if non_cached_bundle_entry.resource:
                    non_cached_resource: Dict[
                        str, Any
                    ] = non_cached_bundle_entry.resource
                    non_cached_resource_id: Optional[str] = non_cached_resource.get(
                        "id"
                    )
                    if non_cached_resource_id:
                        cache.add(
                            resource_type=resource_type,
                            resource_id=non_cached_resource_id,
                            bundle_entry=non_cached_bundle_entry,
                        )

            if cached_response:
                result.append([cached_response])
        elif cached_response:
            result = cached_response
        assert result
        return result, cache_hits

    @abstractmethod
    def separate_bundle_resources(self, separate_bundle_resources: bool):  # type: ignore[no-untyped-def]
        pass

    @abstractmethod
    def create_http_session(self) -> ClientSession:
        pass

    @abstractmethod
    async def _get_with_session_async(
        self,
        *,
        session: Optional[ClientSession],
        page_number: Optional[int] = None,
        ids: Optional[List[str]] = None,
        id_above: Optional[str] = None,
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction] = None,
        additional_parameters: Optional[List[str]] = None,
    ) -> FhirGetResponse:
        pass

    @abstractmethod
    def resource(self, resource: str):  # type: ignore[no-untyped-def]
        pass
