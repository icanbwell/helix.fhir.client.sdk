import json
from abc import ABC
from datetime import datetime
from typing import (
    Dict,
    Optional,
    List,
    Union,
    Any,
    Tuple,
    cast,
    AsyncGenerator,
)

from helix_fhir_client_sdk.dictionary_parser import DictionaryParser
from helix_fhir_client_sdk.fhir_bundle import BundleEntry, Bundle
from helix_fhir_client_sdk.fhir_bundle_appender import FhirBundleAppender
from helix_fhir_client_sdk.graph.graph_definition import (
    GraphDefinition,
    GraphDefinitionLink,
    GraphDefinitionTarget,
)
from helix_fhir_client_sdk.graph.graph_link_parameters import GraphLinkParameters
from helix_fhir_client_sdk.graph.graph_target_parameters import GraphTargetParameters
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.async_parallel_processor.v1.async_parallel_processor import (
    AsyncParallelProcessor,
    ParallelFunctionContext,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder
from helix_fhir_client_sdk.utilities.fhir_scope_parser import FhirScopeParser
from helix_fhir_client_sdk.utilities.request_cache import RequestCache


class SimulatedGraphProcessorMixin(ABC, FhirClientProtocol):
    # noinspection PyPep8Naming,PyUnusedLocal
    async def process_simulate_graph_async(
        self,
        *,
        id_: Union[List[str], str],
        graph_json: Dict[str, Any],
        contained: bool,
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
        request_size: Optional[int] = 1,
        max_concurrent_tasks: Optional[int],
        sort_resources: Optional[bool],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Simulates the $graph query on the FHIR server


        :param separate_bundle_resources:
        :param id_: single id or list of ids (ids can be comma separated too)
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
        :param request_size: No. of resources to request in one FHIR request
        :param max_concurrent_tasks: Optional number of concurrent tasks.  If 1 then the tasks are processed sequentially
        :param sort_resources: Optional flag to sort resources
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
            # first load the start resource
            start: str = graph_definition.start
            response: FhirGetResponse
            cache_hits: int
            response, cache_hits = await self._get_resources_by_parameters_async(
                resource_type=start,
                id_=id_,
                cache=cache,
                scope_parser=scope_parser,
                logger=logger,
            )
            if not response.responses:
                yield response
                return  # no resources to process

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
            parent_link_map: List[
                Tuple[List[GraphDefinitionLink], List[BundleEntry]]
            ] = []
            if graph_definition.link and parent_bundle_entries:
                parent_link_map.append((graph_definition.link, parent_bundle_entries))
            while len(parent_link_map):
                new_parent_link_map: List[
                    Tuple[List[GraphDefinitionLink], List[BundleEntry]]
                ] = []
                for link, parent_bundle_entries in parent_link_map:
                    link_responses: List[FhirGetResponse]
                    async for link_responses in AsyncParallelProcessor(
                        name="process_link_async_parallel_function",
                        max_concurrent_tasks=max_concurrent_tasks,
                    ).process_rows_in_parallel(
                        rows=link,
                        process_row_fn=self.process_link_async_parallel_function,
                        parameters=GraphLinkParameters(
                            parent_bundle_entries=parent_bundle_entries,
                            logger=logger,
                            cache=cache,
                            scope_parser=scope_parser,
                            max_concurrent_tasks=max_concurrent_tasks,
                        ),
                        log_level=self._log_level,
                        parent_link_map=new_parent_link_map,
                        request_size=request_size,
                    ):
                        responses.extend(link_responses)
                parent_link_map = new_parent_link_map
            FhirBundleAppender.append_responses(responses=responses, bundle=bundle)

            bundle = FhirBundleAppender.remove_duplicate_resources(bundle=bundle)

            if sort_resources:
                bundle = FhirBundleAppender.sort_resources(bundle=bundle)

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
            yield response

    # noinspection PyUnusedLocal
    async def process_link_async_parallel_function(
        self,
        context: ParallelFunctionContext,
        row: GraphDefinitionLink,
        parameters: Optional[GraphLinkParameters],
        additional_parameters: Optional[Dict[str, Any]],
    ) -> List[FhirGetResponse]:
        """
        This function is called by AsyncParallelProcessor to process a link in parallel.
        It has to match the function definition of ParallelFunction


        """
        start_time: datetime = datetime.now()
        target_resource_type: Optional[str] = (
            ", ".join([target.type_ for target in row.target]) if row.target else None
        )
        assert parameters
        if parameters.logger:
            parameters.logger.debug(
                f"Processing link"
                + f" | task_index: {context.task_index}/{context.total_task_count}"
                + (
                    f" | path: {row.path}"
                    if row.path
                    else f" | target: {target_resource_type}"
                )
                + f" | parallel_processor: {context.name}"
                + f" | start_time: {start_time}"
            )
        result: List[FhirGetResponse] = []
        link_result: FhirGetResponse
        async for link_result in self._process_link_async(
            link=row,
            parent_bundle_entries=parameters.parent_bundle_entries,
            logger=parameters.logger,
            cache=parameters.cache,
            scope_parser=parameters.scope_parser,
            parent_link_map=(
                additional_parameters["parent_link_map"]
                if additional_parameters
                else []
            ),
            request_size=(
                additional_parameters["request_size"] if additional_parameters else 1
            ),
            max_concurrent_tasks=parameters.max_concurrent_tasks,
        ):
            result.append(link_result)
        end_time: datetime = datetime.now()
        if parameters.logger:
            parameters.logger.debug(
                f"Finished Processing link"
                + f" | task_index: {context.task_index}/{context.total_task_count}"
                + (
                    f" | path: {row.path}"
                    if row.path
                    else f" | target: {target_resource_type}"
                )
                + f" | parallel_processor: {context.name}"
                + f" | end_time: {end_time}"
                + f" | duration: {end_time - start_time}"
                + f" | resource_count: {len(result)}"
            )
        return result

    async def _process_link_async(
        self,
        *,
        link: GraphDefinitionLink,
        parent_bundle_entries: Optional[List[BundleEntry]],
        logger: Optional[FhirLogger],
        cache: RequestCache,
        scope_parser: FhirScopeParser,
        parent_link_map: List[Tuple[List[GraphDefinitionLink], List[BundleEntry]]],
        request_size: int,
        max_concurrent_tasks: Optional[int],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Process a GraphDefinition link object


        :param link: link to process
        :param parent_bundle_entries: list of parent bundle entry
        :param logger: logger to use
        :param cache: cache to use
        :param scope_parser: scope parser to use
        :param max_concurrent_tasks: number of concurrent tasks. If 1 then the tasks are processed sequentially
        :return: list of FhirGetResponse objects
        """
        assert link
        targets: List[GraphDefinitionTarget] = link.target
        target_responses: List[FhirGetResponse]
        async for target_responses in AsyncParallelProcessor(
            name="process_target_async",
            max_concurrent_tasks=max_concurrent_tasks,
        ).process_rows_in_parallel(
            rows=targets,
            process_row_fn=self.process_target_async_parallel_function,
            parameters=GraphTargetParameters(
                path=link.path,
                parent_bundle_entries=parent_bundle_entries,
                logger=logger,
                cache=cache,
                scope_parser=scope_parser,
                max_concurrent_tasks=max_concurrent_tasks,
            ),
            parent_link_map=parent_link_map,
            request_size=request_size,
        ):
            for target_response in target_responses:
                yield target_response

    # noinspection PyUnusedLocal
    async def process_target_async_parallel_function(
        self,
        context: ParallelFunctionContext,
        row: GraphDefinitionTarget,
        parameters: Optional[GraphTargetParameters],
        additional_parameters: Optional[Dict[str, Any]],
    ) -> List[FhirGetResponse]:
        """
        This function is called by AsyncParallelProcessor to process a link in parallel.
        It has to match the function definition of ParallelFunction
        """
        assert parameters
        result: List[FhirGetResponse] = []
        target_result: FhirGetResponse
        async for target_result in self._process_target_async(
            target=row,
            path=parameters.path,
            parent_bundle_entries=parameters.parent_bundle_entries,
            logger=parameters.logger,
            cache=parameters.cache,
            scope_parser=parameters.scope_parser,
            parent_link_map=(
                additional_parameters["parent_link_map"]
                if additional_parameters
                else []
            ),
            request_size=(
                additional_parameters["request_size"] if additional_parameters else 1
            ),
        ):
            result.append(target_result)
        return result

    async def _process_child_group(
        self,
        *,
        id_: Optional[Union[List[str], str]] = None,
        resource_type: str,
        parameters: Optional[List[str]] = None,
        path: Optional[str],
        cache: RequestCache,
        scope_parser: FhirScopeParser,
        logger: Optional[FhirLogger],
    ) -> FhirGetResponse:
        (
            child_response,
            cache_hits,
        ) = await self._get_resources_by_parameters_async(
            resource_type=resource_type,
            id_=id_,
            parameters=parameters,
            cache=cache,
            scope_parser=scope_parser,
            logger=logger,
        )
        if logger:
            logger.info(
                f"Received child resources"
                + f" from parent {resource_type}/{id_}"
                + f" [{path}]"
                + f", count:{len(child_response.get_resource_type_and_ids())}, cached:{cache_hits}"
                + f", {','.join(child_response.get_resource_type_and_ids())}"
            )
        return child_response

    async def _process_target_async(
        self,
        *,
        target: GraphDefinitionTarget,
        path: Optional[str],
        parent_bundle_entries: Optional[List[BundleEntry]],
        logger: Optional[FhirLogger],
        cache: RequestCache,
        scope_parser: FhirScopeParser,
        parent_link_map: List[Tuple[List[GraphDefinitionLink], List[BundleEntry]]],
        request_size: int,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Process a GraphDefinition target


        :param target: target to process
        :param path: path to process
        :param parent_bundle_entries: list of parent bundle entry
        :param logger: logger to use
        :param cache: cache to use
        :param scope_parser: scope parser to use
        :return: list of FhirGetResponse objects
        """
        children: List[BundleEntry] = []
        child_response: FhirGetResponse
        target_type: Optional[str] = target.type_
        reference: Optional[Union[Dict[str, Any], str]] = None
        assert target_type

        # forward link and iterate over list
        if path and "[x]" in path and parent_bundle_entries:
            child_ids = []
            for parent_bundle_entry in parent_bundle_entries:
                parent_resource = parent_bundle_entry.resource
                references: Union[List[Dict[str, Any]], Dict[str, Any], str, None] = (
                    DictionaryParser.get_nested_property(parent_resource, path)
                    if parent_resource
                    else None
                )
                # remove null references
                if references and isinstance(references, list):
                    references = [r for r in references if r is not None]

                if parent_resource and references and target_type:
                    for r in references:
                        reference_id = None
                        # TODO: consider removing assumption of "reference" and require as part of path instead
                        if isinstance(r, dict) and "reference" in r:
                            reference_id = r["reference"]
                        elif isinstance(r, str) and r.startswith("Binary/"):
                            reference_id = r
                        if reference_id:
                            reference_parts = reference_id.split("/")
                            if (
                                reference_parts[0] == target_type
                                and reference_parts[1]
                                and reference_parts[1] not in child_ids
                            ):
                                child_ids.append(reference_parts[1])
                        if request_size and len(child_ids) == request_size:
                            child_response = await self._process_child_group(
                                resource_type=target_type,
                                id_=child_ids,
                                path=path,
                                cache=cache,
                                scope_parser=scope_parser,
                                logger=logger,
                            )
                            yield child_response
                            children.extend(child_response.get_bundle_entries())
                            child_ids = []
            if child_ids:
                child_response = await self._process_child_group(
                    resource_type=target_type,
                    id_=child_ids,
                    path=path,
                    cache=cache,
                    scope_parser=scope_parser,
                    logger=logger,
                )
                yield child_response
                children.extend(child_response.get_bundle_entries())
        elif path and parent_bundle_entries and target_type:
            child_ids = []
            for parent_bundle_entry in parent_bundle_entries:
                parent_resource = parent_bundle_entry.resource
                reference = parent_resource.get(path, {}) if parent_resource else None
                if reference and "reference" in reference:
                    reference_id = reference["reference"]
                    reference_parts = reference_id.split("/")
                    if (
                        reference_parts[0] == target_type
                        and reference_parts[1]
                        and reference_parts[1] not in child_ids
                    ):
                        child_ids.append(reference_parts[1])
                    if request_size and len(child_ids) == request_size:
                        child_response = await self._process_child_group(
                            resource_type=target_type,
                            id_=child_ids,
                            path=path,
                            cache=cache,
                            scope_parser=scope_parser,
                            logger=logger,
                        )
                        yield child_response
                        children.extend(child_response.get_bundle_entries())
                        child_ids = []
            if child_ids:
                child_response = await self._process_child_group(
                    resource_type=target_type,
                    id_=child_ids,
                    path=path,
                    cache=cache,
                    scope_parser=scope_parser,
                    logger=logger,
                )
                yield child_response
                children.extend(child_response.get_bundle_entries())

        elif target.params:  # reverse path
            # for a reverse link, get the ids of the current resource, put in a view and
            # add a stage to get that
            param_list: List[str] = target.params.split("&")
            ref_param = [p for p in param_list if p.endswith("{ref}")][0]
            additional_parameters = [p for p in param_list if not p.endswith("{ref}")]
            property_name: str = ref_param.split("=")[0]
            if parent_bundle_entries and property_name and target_type:
                parent_ids = []
                for parent_bundle_entry in parent_bundle_entries:
                    parent_id = (
                        parent_bundle_entry.resource.get("id")
                        if parent_bundle_entry.resource
                        else None
                    )
                    if parent_id and parent_id not in parent_ids:
                        parent_ids.append(parent_id)
                    if request_size and len(parent_ids) == request_size:
                        request_parameters = [
                            f"{property_name}={','.join(parent_ids)}"
                        ] + additional_parameters
                        child_response = await self._process_child_group(
                            resource_type=target_type,
                            parameters=request_parameters,
                            path=path,
                            cache=cache,
                            scope_parser=scope_parser,
                            logger=logger,
                        )
                        yield child_response
                        children.extend(child_response.get_bundle_entries())
                        parent_ids = []
                if parent_ids:
                    request_parameters = [
                        f"{property_name}={','.join(parent_ids)}"
                    ] + additional_parameters
                    child_response = await self._process_child_group(
                        resource_type=target_type,
                        parameters=request_parameters,
                        path=path,
                        cache=cache,
                        scope_parser=scope_parser,
                        logger=logger,
                    )
                    yield child_response
                    children.extend(child_response.get_bundle_entries())
        if target.link:
            parent_link_map.append((target.link, children))

    async def _get_resources_by_parameters_async(
        self: FhirClientProtocol,
        *,
        id_: Optional[Union[List[str], str]] = None,
        resource_type: str,
        parameters: Optional[List[str]] = None,
        cache: RequestCache,
        scope_parser: FhirScopeParser,
        logger: Optional[FhirLogger],
    ) -> Tuple[FhirGetResponse, int]:
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
                url=(
                    cached_bundle_entries[0].request.url
                    if cached_bundle_entries[0].request
                    else ""
                ),
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
            async for (
                result1
            ) in self._get_with_session_async(  # type:ignore[attr-defined]
                page_number=None,
                ids=non_cached_id_list,
                additional_parameters=parameters,
                id_above=None,
                fn_handle_streaming_chunk=None,
                resource_type=resource_type,
            ):
                result = result1
            assert result
            non_cached_bundle_entry: BundleEntry
            for non_cached_bundle_entry in result.get_bundle_entries():
                if non_cached_bundle_entry.resource:
                    non_cached_resource: Dict[str, Any] = (
                        non_cached_bundle_entry.resource
                    )
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
                result.append(cached_response)
        elif cached_response:
            result = cached_response
        assert result
        return result, cache_hits

    # noinspection PyPep8Naming
    async def simulate_graph_async(
        self,
        *,
        id_: Union[List[str], str],
        graph_json: Dict[str, Any],
        contained: bool,
        separate_bundle_resources: bool = False,
        restrict_to_scope: Optional[str] = None,
        restrict_to_resources: Optional[List[str]] = None,
        restrict_to_capability_statement: Optional[str] = None,
        retrieve_and_restrict_to_capability_statement: Optional[bool] = None,
        ifModifiedSince: Optional[datetime] = None,
        eTag: Optional[str] = None,
        request_size: Optional[int] = 1,
        max_concurrent_tasks: Optional[int] = 1,
        sort_resources: Optional[bool] = False,
    ) -> FhirGetResponse:
        """
        Simulates the $graph query on the FHIR server


        :param separate_bundle_resources:
        :param id_: single id or list of ids (ids can be comma separated too)
        :param graph_json: definition of a graph to execute
        :param contained: whether we should return the related resources as top level list or nest them inside their
                            parent resources in a contained property
        :param restrict_to_scope: Optional scope to restrict to
        :param restrict_to_resources: Optional list of resources to restrict to
        :param restrict_to_capability_statement: Optional capability statement to restrict to
        :param retrieve_and_restrict_to_capability_statement: Optional capability statement to retrieve and restrict to
        :param ifModifiedSince: Optional datetime to use for If-Modified-Since header
        :param eTag: Optional ETag to use for If-None-Match header
        :param request_size: Optional Count of resoucres to request in one request
        :param max_concurrent_tasks: Optional number of concurrent tasks.  If 1 then the tasks are processed sequentially.
        :param sort_resources: Optional flag to sort resources
        :return: FhirGetResponse
        """
        if contained:
            if not self._additional_parameters:
                self.additional_parameters([])
            assert self._additional_parameters is not None
            self._additional_parameters.append("contained=true")

        result: Optional[FhirGetResponse] = await FhirGetResponse.from_async_generator(
            self.process_simulate_graph_async(
                id_=id_,
                graph_json=graph_json,
                contained=contained,
                separate_bundle_resources=separate_bundle_resources,
                restrict_to_scope=restrict_to_scope,
                restrict_to_resources=restrict_to_resources,
                restrict_to_capability_statement=restrict_to_capability_statement,
                retrieve_and_restrict_to_capability_statement=retrieve_and_restrict_to_capability_statement,
                ifModifiedSince=ifModifiedSince,
                eTag=eTag,
                url=self._url,
                expand_fhir_bundle=self._expand_fhir_bundle,
                logger=self._logger,
                auth_scopes=self._auth_scopes,
                request_size=request_size,
                max_concurrent_tasks=max_concurrent_tasks,
                sort_resources=sort_resources,
            )
        )
        assert result, "No result returned from simulate_graph_async"
        return result

    # noinspection PyPep8Naming
    async def simulate_graph_streaming_async(
        self,
        *,
        id_: Union[List[str], str],
        graph_json: Dict[str, Any],
        contained: bool,
        separate_bundle_resources: bool = False,
        restrict_to_scope: Optional[str] = None,
        restrict_to_resources: Optional[List[str]] = None,
        restrict_to_capability_statement: Optional[str] = None,
        retrieve_and_restrict_to_capability_statement: Optional[bool] = None,
        ifModifiedSince: Optional[datetime] = None,
        eTag: Optional[str] = None,
        request_size: Optional[int] = 1,
        max_concurrent_tasks: Optional[int] = 1,
        sort_resources: Optional[bool] = False,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Simulates the $graph query on the FHIR server


        :param separate_bundle_resources:
        :param id_: single id or list of ids (ids can be comma separated too)
        :param graph_json: definition of a graph to execute
        :param contained: whether we should return the related resources as top level list or nest them inside their
                            parent resources in a contained property
        :param restrict_to_scope: Optional scope to restrict to
        :param restrict_to_resources: Optional list of resources to restrict to
        :param restrict_to_capability_statement: Optional capability statement to restrict to
        :param retrieve_and_restrict_to_capability_statement: Optional capability statement to retrieve and restrict to
        :param ifModifiedSince: Optional datetime to use for If-Modified-Since header
        :param eTag: Optional ETag to use for If-None-Match header
        :param request_size: Optional Count of resoucres to request in one request
        :param max_concurrent_tasks: Optional number of concurrent tasks.  If 1 then the tasks are processed sequentially
        :param sort_resources: Optional flag to sort resources
        :return: FhirGetResponse
        """
        if contained:
            if not self._additional_parameters:
                self.additional_parameters([])
            assert self._additional_parameters is not None
            self._additional_parameters.append("contained=true")

        async for r in self.process_simulate_graph_async(
            id_=id_,
            graph_json=graph_json,
            contained=contained,
            separate_bundle_resources=separate_bundle_resources,
            restrict_to_scope=restrict_to_scope,
            restrict_to_resources=restrict_to_resources,
            restrict_to_capability_statement=restrict_to_capability_statement,
            retrieve_and_restrict_to_capability_statement=retrieve_and_restrict_to_capability_statement,
            ifModifiedSince=ifModifiedSince,
            eTag=eTag,
            url=self._url,
            expand_fhir_bundle=self._expand_fhir_bundle,
            logger=self._logger,
            auth_scopes=self._auth_scopes,
            request_size=request_size,
            max_concurrent_tasks=max_concurrent_tasks,
            sort_resources=sort_resources,
        ):
            yield r
