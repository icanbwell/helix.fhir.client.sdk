import json
from abc import ABC
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from logging import Logger
from typing import Any, cast
from urllib.parse import quote

from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from compressedfhir.fhir.fhir_resource import FhirResource

from helix_fhir_client_sdk.dictionary_parser import DictionaryParser
from helix_fhir_client_sdk.graph.graph_definition import (
    GraphDefinition,
    GraphDefinitionLink,
    GraphDefinitionTarget,
)
from helix_fhir_client_sdk.graph.graph_link_parameters import GraphLinkParameters
from helix_fhir_client_sdk.graph.graph_target_parameters import GraphTargetParameters
from helix_fhir_client_sdk.responses.fhir_client_protocol import FhirClientProtocol
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_bundle_response import (
    FhirGetBundleResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_error_response import (
    FhirGetErrorResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_list_by_resource_type_response import (
    FhirGetListByResourceTypeResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_list_response import (
    FhirGetListResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_response_factory import (
    FhirGetResponseFactory,
)
from helix_fhir_client_sdk.utilities.async_parallel_processor.v1.async_parallel_processor import (
    AsyncParallelProcessor,
    ParallelFunctionContext,
)
from helix_fhir_client_sdk.utilities.cache.request_cache import RequestCache
from helix_fhir_client_sdk.utilities.cache.request_cache_entry import RequestCacheEntry
from helix_fhir_client_sdk.utilities.fhir_scope_parser import FhirScopeParser
from helix_fhir_client_sdk.utilities.hash_util import ResourceHash


class SimulatedGraphProcessorMixin(ABC, FhirClientProtocol):
    """
    A mixin class for advanced FHIR graph query processing.

    This class provides sophisticated methods for:
    - Simulating graph-based resource queries
    - Parallel processing of FHIR resources
    - Caching and optimizing resource retrieval
    - Handling complex graph traversal scenarios
    """

    # noinspection PyPep8Naming,PyUnusedLocal
    async def process_simulate_graph_async(
        self,
        *,
        id_: list[str] | str,
        graph_json: dict[str, Any],
        contained: bool,
        separate_bundle_resources: bool = False,
        restrict_to_scope: str | None = None,
        restrict_to_resources: list[str] | None = None,
        restrict_to_capability_statement: str | None = None,
        retrieve_and_restrict_to_capability_statement: bool | None = None,
        ifModifiedSince: datetime | None = None,
        eTag: str | None = None,
        logger: Logger | None,
        url: str | None,
        expand_fhir_bundle: bool | None,
        auth_scopes: list[str] | None,
        request_size: int | None = 1,
        max_concurrent_tasks: int | None,
        sort_resources: bool | None,
        add_cached_bundles_to_result: bool = True,
        input_cache: RequestCache | None = None,
        compare_hash: bool = True,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Asynchronously simulate a FHIR $graph query with advanced processing capabilities.

        This method is the core of graph-based resource traversal, supporting:
        - Parallel resource retrieval
        - Caching mechanisms
        - Scope-based filtering
        - Flexible resource bundling

        Key Processing Steps:
        1. Validate and parse graph definition
        2. Parse authentication scopes
        3. Retrieve start resources
        4. Process graph links and targets in parallel
        5. Handle caching and resource filtering

        Args:
            id_: Resource identifier(s) to query
            graph_json: Graph definition as a dictionary
            contained: Whether to nest related resources or return as top-level
            separate_bundle_resources: Flag to separate bundle resources
            restrict_to_scope: Optional scope restriction
            restrict_to_resources: Optional resource type restrictions
            request_size: Number of resources to fetch in a single request
            max_concurrent_tasks: Maximum parallel processing tasks
            sort_resources: Flag to sort retrieved resources
            auth_scopes: List of authentication scopes for resource access
            url: Optional URL for the FHIR server
            expand_fhir_bundle: Flag to expand FHIR bundle
            ifModifiedSince: Optional timestamp for conditional requests
            eTag: Optional ETag for conditional requests
            logger: Optional logger for debugging
            retrieve_and_restrict_to_capability_statement: Flag to retrieve and restrict to capability statement
            restrict_to_capability_statement: Optional capability statement restriction
            contained: Flag to include contained resources
            add_cached_bundles_to_result: Optional flag to add cached bundles to result
            input_cache: Optional cache for resource retrieval
            compare_hash: Flag to compare resource hashes for changes

        Yields:
            FhirGetResponse objects representing retrieved resources
        """
        # Validate graph definition input
        assert graph_json, "Graph JSON must be provided"
        graph_definition: GraphDefinition = GraphDefinition.from_dict(graph_json)
        assert isinstance(graph_definition, GraphDefinition)
        assert graph_definition.start, "Graph definition must have a start resource"

        # Parse authentication scopes for resource access control
        scope_parser: FhirScopeParser = FhirScopeParser(scopes=auth_scopes)

        # Ensure bundle resources are not separated by default
        self.separate_bundle_resources(False)

        # Log initial query parameters for debugging
        if logger:
            logger.info(
                f"FhirClient.simulate_graph_async() "
                f"id_={id_}, "
                f"contained={contained}, "
                f"separate_bundle_resources={separate_bundle_resources}, "
                f"request_size={request_size}, "
                f"max_concurrent_tasks={max_concurrent_tasks}, "
                f"expand_fhir_bundle={expand_fhir_bundle}, "
                f"ifModifiedSince={ifModifiedSince.isoformat() if ifModifiedSince else None}, "
                f"eTag={eTag}, "
            )

        # Normalize input to a list of IDs, handling comma-separated strings
        if not isinstance(id_, list):
            id_ = id_.split(",")

        # Track resources that don't support ID-based search
        id_search_unsupported_resources: list[str] = []
        cache: RequestCache = input_cache if input_cache is not None else RequestCache()
        async with cache:
            # Retrieve start resources based on graph definition
            start: str = graph_definition.start
            parent_response: FhirGetResponse
            cache_hits: int
            parent_response, cache_hits = await self._get_resources_by_parameters_async(
                resource_type=start,
                id_=id_,
                cache=cache,
                scope_parser=scope_parser,
                logger=logger,
                id_search_unsupported_resources=id_search_unsupported_resources,
                add_cached_bundles_to_result=add_cached_bundles_to_result,
                compare_hash=compare_hash,
            )

            # If no parent resources found, yield empty response and exit
            parent_response_resource_count = parent_response.get_resource_count()
            if parent_response_resource_count == 0:
                yield parent_response
                return  # no resources to process

            # Log parent resource retrieval details
            if logger:
                logger.info(
                    f"FhirClient.simulate_graph_async() "
                    f"got parent resources: {parent_response_resource_count} "
                    f"cached:{cache_hits}"
                )

            # Prepare parent bundle entries for further processing
            parent_bundle_entries: FhirBundleEntryList = parent_response.get_bundle_entries()

            if logger:
                logger.info(
                    f"FhirClient.simulate_graph_async() got parent resources: {parent_response_resource_count} "
                    + f"cached:{cache_hits}"
                )

            # now process the graph links
            child_responses: list[FhirGetResponse] = []
            parent_link_map: list[tuple[list[GraphDefinitionLink], FhirBundleEntryList]] = []

            # Add initial graph links if defined
            if graph_definition.link and parent_bundle_entries:
                parent_link_map.append((graph_definition.link, parent_bundle_entries))

            # Process graph links in parallel
            while len(parent_link_map):
                new_parent_link_map: list[tuple[list[GraphDefinitionLink], FhirBundleEntryList]] = []

                # Parallel processing of links for each parent bundle
                for link, parent_bundle_entries in parent_link_map:
                    link_responses: list[FhirGetResponse]
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
                        id_search_unsupported_resources=id_search_unsupported_resources,
                        add_cached_bundles_to_result=add_cached_bundles_to_result,
                        ifModifiedSince=ifModifiedSince,
                    ):
                        child_responses.extend(link_responses)

                # Update parent link map for next iteration
                parent_link_map = new_parent_link_map

            # Combine and process responses
            parent_response = cast(FhirGetBundleResponse, parent_response.extend(child_responses))
            parent_response = parent_response.remove_duplicates()

            # Optional resource sorting
            if sort_resources:
                parent_response = parent_response.sort_resources()

            # Prepare final response based on bundling preferences
            full_response: FhirGetResponse
            if separate_bundle_resources:
                full_response = FhirGetListByResourceTypeResponse.from_response(other_response=parent_response)
            elif expand_fhir_bundle:
                full_response = FhirGetListResponse.from_response(other_response=parent_response)
            else:
                full_response = parent_response

            # Set response URL
            full_response.url = url or parent_response.url

            # Log cache performance
            if logger:
                logger.info(
                    f"Request Cache for: id_={id_}, "
                    f"start={graph_definition.start}, "
                    f"hits: {cache.cache_hits}, "
                    f"misses: {cache.cache_misses}"
                )

            # Yield the final response
            yield full_response

    # noinspection PyUnusedLocal
    async def process_link_async_parallel_function(
        self,
        context: ParallelFunctionContext,
        row: GraphDefinitionLink,
        parameters: GraphLinkParameters | None,
        additional_parameters: dict[str, Any] | None,
    ) -> list[FhirGetResponse]:
        """
        Parallel processing function for graph definition links.

        This method is designed to be used with AsyncParallelProcessor to process
        graph links concurrently, improving performance for complex FHIR resource
        graph traversals.

        Key Responsibilities:
        - Process individual graph links in parallel
        - Track and log processing details
        - Handle resource retrieval for each link
        - Manage parallel processing context

        Args:
            context: Parallel processing context information
            row: Current GraphDefinitionLink being processed
            parameters: Parameters for link processing
            additional_parameters: Extra parameters for extended processing

        Returns:
            List of FhirGetResponse objects retrieved during link processing
        """
        # Record the start time for performance tracking
        start_time: datetime = datetime.now()

        # Determine the target resource type(s) for logging and tracking
        target_resource_type: str | None = ", ".join([target.type_ for target in row.target]) if row.target else None

        # Validate input parameters
        assert parameters, "Processing parameters must be provided"

        # Log debug information about the current link processing
        if parameters.logger:
            parameters.logger.debug(
                "Processing link"
                + f" | task_index: {context.task_index}/{context.total_task_count}"
                + (f" | path: {row.path}" if row.path else f" | target: {target_resource_type}")
                + f" | parallel_processor: {context.name}"
                + f" | start_time: {start_time}"
            )

        # Initialize result list to store retrieved responses
        result: list[FhirGetResponse] = []

        # Process the link asynchronously and collect responses
        link_result: FhirGetResponse
        async for link_result in self._process_link_async(
            link=row,
            parent_bundle_entries=parameters.parent_bundle_entries,
            logger=parameters.logger,
            cache=parameters.cache,
            scope_parser=parameters.scope_parser,
            # Handle parent link map from additional parameters
            parent_link_map=(additional_parameters["parent_link_map"] if additional_parameters else []),
            # Determine request size, default to 1 if not specified
            request_size=(additional_parameters["request_size"] if additional_parameters else 1),
            # Track unsupported resources for ID-based search
            id_search_unsupported_resources=(
                additional_parameters["id_search_unsupported_resources"] if additional_parameters else []
            ),
            max_concurrent_tasks=parameters.max_concurrent_tasks,
            add_cached_bundles_to_result=(
                additional_parameters.get("add_cached_bundles_to_result", True) if additional_parameters else True
            ),
            ifModifiedSince=(additional_parameters.get("ifModifiedSince", None) if additional_parameters else None),
        ):
            # Collect each link result
            result.append(link_result)

        # Record end time for performance tracking
        end_time: datetime = datetime.now()

        # Log detailed processing information
        if parameters.logger:
            parameters.logger.debug(
                "Finished Processing link"
                + f" | task_index: {context.task_index}/{context.total_task_count}"
                + (f" | path: {row.path}" if row.path else f" | target: {target_resource_type}")
                + f" | parallel_processor: {context.name}"
                + f" | end_time: {end_time}"
                + f" | duration: {end_time - start_time}"
                + f" | resource_count: {len(result)}"
            )

        # Return the list of retrieved responses
        return result

    async def _process_link_async(
        self,
        *,
        link: GraphDefinitionLink,
        parent_bundle_entries: FhirBundleEntryList | None,
        logger: Logger | None,
        cache: RequestCache,
        scope_parser: FhirScopeParser,
        parent_link_map: list[tuple[list[GraphDefinitionLink], FhirBundleEntryList]],
        request_size: int,
        id_search_unsupported_resources: list[str],
        max_concurrent_tasks: int | None,
        add_cached_bundles_to_result: bool = True,
        ifModifiedSince: datetime | None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Process a GraphDefinition link object with advanced traversal capabilities.

        This method is a core component of the graph-based resource retrieval process,
        responsible for:
        - Identifying and processing link targets
        - Parallel processing of targets
        - Managing complex resource graph traversals

        Key Processing Steps:
        1. Extract targets from the link
        2. Use AsyncParallelProcessor to process targets concurrently
        3. Yield retrieved responses
        4. Manage parent link mapping for further traversal

        Args:
            link: GraphDefinitionLink to process
            parent_bundle_entries: List of parent bundle entries
            logger: Optional logger for debugging
            cache: Request cache for optimizing resource retrieval
            scope_parser: Scope-based access control parser
            parent_link_map: Mapping for tracking parent links in graph traversal
            request_size: Number of resources to retrieve in a single request
            id_search_unsupported_resources: List of resources with limited ID search
            max_concurrent_tasks: Maximum number of concurrent processing tasks
            add_cached_bundles_to_result: Flag to add cached bundles to result
            ifModifiedSince: Optional timestamp for conditional requests

        Yields:
            FhirGetResponse objects for each processed target
        """
        # Validate input link
        assert link, "GraphDefinitionLink must be provided"

        if self._logger:
            self._logger.debug(f"Processing link: {link.path} ")

        # Extract targets from the link
        targets: list[GraphDefinitionTarget] = link.target
        target_responses: list[FhirGetResponse]
        async for target_responses in AsyncParallelProcessor(
            name="process_target_async",
            max_concurrent_tasks=max_concurrent_tasks,
        ).process_rows_in_parallel(
            # Rows to process (targets from the link)
            rows=targets,
            # Parallel processing function for targets
            process_row_fn=self.process_target_async_parallel_function,
            # Parameters for target processing
            parameters=GraphTargetParameters(
                path=link.path,
                parent_bundle_entries=parent_bundle_entries,
                logger=logger,
                cache=cache,
                scope_parser=scope_parser,
                max_concurrent_tasks=max_concurrent_tasks,
            ),
            # Additional parameters for extended processing
            parent_link_map=parent_link_map,
            request_size=request_size,
            id_search_unsupported_resources=id_search_unsupported_resources,
            add_cached_bundles_to_result=add_cached_bundles_to_result,
            ifModifiedSince=ifModifiedSince,
        ):
            # Yield each target response individually
            for target_response in target_responses:
                yield target_response

    # noinspection PyUnusedLocal
    async def process_target_async_parallel_function(
        self,
        context: ParallelFunctionContext,
        row: GraphDefinitionTarget,
        parameters: GraphTargetParameters | None,
        additional_parameters: dict[str, Any] | None,
    ) -> list[FhirGetResponse]:
        """
        Parallel processing function for individual graph definition targets.

        This method is designed to:
        - Process a single target in the context of parallel processing
        - Retrieve resources for a specific target
        - Manage performance tracking and logging
        - Handle complex resource graph traversals

        Key Responsibilities:
        - Execute target-specific resource retrieval
        - Track processing performance
        - Log detailed processing information
        - Manage parallel processing context

        Args:
            context: Parallel processing context information
            row: Current GraphDefinitionTarget being processed
            parameters: Parameters for target processing
            additional_parameters: Extra parameters for extended processing

        Returns:
            List of FhirGetResponse objects retrieved for the target
        """
        # Validate input parameters
        assert parameters, "Processing parameters must be provided"

        # Initialize result list to store retrieved responses
        result: list[FhirGetResponse] = []

        # Process the target asynchronously and collect responses
        target_result: FhirGetResponse
        async for target_result in self._process_target_async(
            # Target to process
            target=row,
            # Path from the parent link
            path=parameters.path,
            # Parent bundle entries for context
            parent_bundle_entries=parameters.parent_bundle_entries,
            # Logging support
            logger=parameters.logger,
            # Caching mechanism
            cache=parameters.cache,
            # Scope-based access control
            scope_parser=parameters.scope_parser,
            # Parent link map for further graph traversal
            parent_link_map=(additional_parameters["parent_link_map"] if additional_parameters else []),
            # Request size configuration
            request_size=(additional_parameters["request_size"] if additional_parameters else 1),
            # Track resources with limited ID search capabilities
            id_search_unsupported_resources=(
                additional_parameters["id_search_unsupported_resources"] if additional_parameters else []
            ),
            add_cached_bundles_to_result=(
                additional_parameters.get("add_cached_bundles_to_result", True) if additional_parameters else True
            ),
            ifModifiedSince=(additional_parameters.get("ifModifiedSince", None) if additional_parameters else None),
        ):
            # Collect each target result
            result.append(target_result)

        # Return the list of retrieved responses
        return result

    async def _process_child_group(
        self,
        *,
        id_: list[str] | str | None = None,
        resource_type: str,
        parent_ids: list[str],
        parent_resource_type: str,
        parameters: list[str] | None = None,
        path: str | None,
        cache: RequestCache,
        scope_parser: FhirScopeParser,
        logger: Logger | None,
        id_search_unsupported_resources: list[str],
        add_cached_bundles_to_result: bool = True,
    ) -> FhirGetResponse:
        """
        Retrieve a group of child resources with advanced retrieval and logging capabilities.

        This method is a core component of graph-based resource traversal, responsible for:
        - Fetching child resources based on parent context
        - Implementing caching and scope-based retrieval
        - Providing detailed logging and performance tracking

        Key Processing Steps:
        1. Retrieve resources using provided parameters
        2. Apply caching mechanism
        3. Log detailed retrieval information
        4. Handle various resource retrieval scenarios

        Args:
            id_: Optional resource identifier(s)
            resource_type: Type of resources to retrieve
            parent_ids: List of parent resource identifiers
            parent_resource_type: Type of parent resources
            parameters: Optional additional search parameters
            path: Optional path for resource retrieval
            cache: Request cache for optimizing resource retrieval
            scope_parser: Scope-based access control parser
            logger: Optional logger for debugging
            id_search_unsupported_resources: List of resources with limited ID search

        Returns:
            FhirGetResponse containing retrieved child resources
        """
        # Retrieve resources using async method with parameters
        (
            child_response,  # Retrieved child resources
            cache_hits,  # Number of cache hits during retrieval
        ) = await self._get_resources_by_parameters_async(
            # Resource type to retrieve
            resource_type=resource_type,
            # Resource identifiers
            id_=id_,
            # Additional search parameters
            parameters=parameters,
            # Caching mechanism
            cache=cache,
            # Scope-based access control
            scope_parser=scope_parser,
            # Optional logger
            logger=logger,
            # Track resources with limited ID search
            id_search_unsupported_resources=id_search_unsupported_resources,
            add_cached_bundles_to_result=add_cached_bundles_to_result,
        )

        # Log detailed retrieval information if logger is available
        if logger:
            logger.info(
                # Construct a detailed log message with retrieval context
                "Received child resources"
                + f" from parent {parent_resource_type}/{parent_ids}"
                + f" path:[{path}]. id_:{id_}. resource_type:{resource_type}"
                + f", count:{len(child_response.get_resource_type_and_ids())}"
                + f", cached:{cache_hits}"
                + f", {','.join(child_response.get_resource_type_and_ids())}"
            )

        # Return the retrieved child resources
        return child_response

    async def _process_target_async(
        self,
        *,
        target: GraphDefinitionTarget,
        path: str | None,
        parent_bundle_entries: FhirBundleEntryList | None,
        logger: Logger | None,
        cache: RequestCache,
        scope_parser: FhirScopeParser,
        parent_link_map: list[tuple[list[GraphDefinitionLink], list[FhirBundleEntry]]],
        request_size: int,
        id_search_unsupported_resources: list[str],
        add_cached_bundles_to_result: bool = True,
        ifModifiedSince: datetime | None = None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        """
        Process a GraphDefinition target


        :param target: target to process
        :param path: path to process
        :param parent_bundle_entries: list of parent bundle entry
        :param logger: logger to use
        :param cache: cache to use
        :param scope_parser: scope parser to use
        :param add_cached_bundles_to_result: whether to add cached bundles to result
        :param request_size: number of resources to request at once
        :param id_search_unsupported_resources: list of resources that do not support id search
        :param ifModifiedSince: ifModifiedSince to use
        :return: list of FhirGetResponse objects
        """
        children: list[FhirBundleEntry] = []
        child_response: FhirGetResponse
        target_type: str | None = target.type_
        assert target_type
        parent_resource_type: str = ""
        parent_ids: list[str] = []

        if self._logger:
            self._logger.debug(
                f"Processing target: {target_type} "
                f"from parent {parent_resource_type}/{parent_ids}"
                f" path:[{path}]"
                f"params: {target.params}"
            )

        # forward link and iterate over list
        if path and "[x]" in path and parent_bundle_entries:
            child_ids = []
            for parent_bundle_entry in parent_bundle_entries:
                parent_resource = parent_bundle_entry.resource
                references: list[dict[str, Any]] | dict[str, Any] | str | None = (
                    DictionaryParser.get_nested_property(parent_resource.dict(), path) if parent_resource else None
                )
                # remove null references
                if references and isinstance(references, list):
                    references = [r for r in references if r is not None]

                if parent_resource and references and target_type:
                    parent_resource_type = parent_resource.get("resourceType", "")
                    parent_ids.append(parent_resource.get("id", ""))
                    for r in references:
                        reference_id = None
                        # TODO: consider removing assumption of "reference" and require as part of path instead
                        if isinstance(r, dict) and "reference" in r:
                            reference_id = r["reference"]
                        elif isinstance(r, str) and r.startswith("Binary/"):
                            reference_id = r
                        if reference_id:
                            reference_parts = reference_id.split("/")
                            if target_type in reference_parts:
                                if reference_parts[-1] and reference_parts[-1] not in child_ids:
                                    child_ids.append(reference_parts[-1])
                                # If we receive a reference like "example.com/Procedure/1234/"
                                elif (
                                    len(reference_parts) > 2
                                    and reference_parts[-2]
                                    and reference_parts[-2] not in child_ids
                                ):
                                    child_ids.append(reference_parts[-2])
                        if request_size and len(child_ids) == request_size:
                            child_response = await self._process_child_group(
                                resource_type=target_type,
                                id_=child_ids,
                                parent_ids=parent_ids,
                                parent_resource_type=parent_resource_type,
                                path=path,
                                cache=cache,
                                scope_parser=scope_parser,
                                logger=logger,
                                id_search_unsupported_resources=id_search_unsupported_resources,
                                add_cached_bundles_to_result=add_cached_bundles_to_result,
                            )
                            yield child_response
                            children.extend(child_response.get_bundle_entries())
                            child_ids = []
                            parent_ids = []
            if child_ids:
                child_response = await self._process_child_group(
                    resource_type=target_type,
                    id_=child_ids,
                    parent_ids=parent_ids,
                    parent_resource_type=parent_resource_type,
                    path=path,
                    cache=cache,
                    scope_parser=scope_parser,
                    logger=logger,
                    id_search_unsupported_resources=id_search_unsupported_resources,
                    add_cached_bundles_to_result=add_cached_bundles_to_result,
                )
                yield child_response
                children.extend(child_response.get_bundle_entries())
        elif path and parent_bundle_entries and target_type:
            child_ids = []
            for parent_bundle_entry in parent_bundle_entries:
                parent_resource = parent_bundle_entry.resource
                if parent_resource is not None:
                    with parent_resource.transaction():
                        reference = parent_resource.get(path, None)
                        if reference is not None and "reference" in reference:
                            parent_ids.append(parent_resource.get("id", ""))
                            parent_resource_type = parent_resource.get("resourceType", "")
                            # noinspection PyUnresolvedReferences
                            reference_id = reference["reference"]
                            reference_parts = reference_id.split("/")
                            if target_type in reference_parts:
                                if reference_parts[-1] and reference_parts[-1] not in child_ids:
                                    child_ids.append(reference_parts[-1])
                                # If we receive a reference like "example.com/Procedure/1234/"
                                elif (
                                    len(reference_parts) > 2
                                    and reference_parts[-2]
                                    and reference_parts[-2] not in child_ids
                                ):
                                    child_ids.append(reference_parts[-2])
                            if request_size and len(child_ids) == request_size:
                                child_response = await self._process_child_group(
                                    resource_type=target_type,
                                    id_=child_ids,
                                    parent_ids=parent_ids,
                                    parent_resource_type=parent_resource_type,
                                    path=path,
                                    cache=cache,
                                    scope_parser=scope_parser,
                                    logger=logger,
                                    id_search_unsupported_resources=id_search_unsupported_resources,
                                    add_cached_bundles_to_result=add_cached_bundles_to_result,
                                )
                                yield child_response
                                children.extend(child_response.get_bundle_entries())
                                child_ids = []
                                parent_ids = []
            if child_ids:
                child_response = await self._process_child_group(
                    resource_type=target_type,
                    id_=child_ids,
                    parent_ids=parent_ids,
                    parent_resource_type=parent_resource_type,
                    path=path,
                    cache=cache,
                    scope_parser=scope_parser,
                    logger=logger,
                    id_search_unsupported_resources=id_search_unsupported_resources,
                    add_cached_bundles_to_result=add_cached_bundles_to_result,
                )
                yield child_response
                children.extend(child_response.get_bundle_entries())

        elif target.params:  # reverse path
            # for a reverse link, get the ids of the current resource, put in a view and
            # add a stage to get that
            param_list: list[str] = target.params.split("&")
            ref_param = [p for p in param_list if p.endswith("{ref}")][0]
            # replace any parameters with {ifModifiedSince} with the actual value
            if ifModifiedSince:
                if_modified_since_date: datetime = ifModifiedSince
                # if ifModifiedSince is missing timezone then set it to utc
                if if_modified_since_date.tzinfo is None:
                    if_modified_since_date = ifModifiedSince.replace(tzinfo=UTC)
                else:
                    if_modified_since_date = ifModifiedSince.astimezone(UTC)
                # convert to isoformat
                if_modified_since_isoformat = quote(if_modified_since_date.date().isoformat())
                param_list = [p.replace("{ifModifiedSince}", if_modified_since_isoformat) for p in param_list]
            else:
                # remove any parameters with {ifModifiedSince}
                param_list = [p for p in param_list if not p.endswith("{ifModifiedSince}")]
            # now get all the parameters that are not {ref}
            additional_parameters = [p for p in param_list if not p.endswith("{ref}")]
            # get the property name of the ref parameter
            property_name: str = ref_param.split("=")[0]
            if parent_bundle_entries and property_name and target_type:
                for parent_bundle_entry in parent_bundle_entries:
                    parent_resource = parent_bundle_entry.resource
                    if parent_resource:
                        parent_id = quote(parent_resource.get("id", ""))
                        parent_resource_type = parent_resource.get("resourceType", "")
                        if parent_id and parent_id not in parent_ids:
                            parent_ids.append(parent_id)
                    if request_size and len(parent_ids) == request_size:
                        request_parameters = [f"{property_name}={','.join(parent_ids)}"] + additional_parameters
                        child_response = await self._process_child_group(
                            resource_type=target_type,
                            parent_ids=parent_ids,
                            parent_resource_type=parent_resource_type,
                            parameters=request_parameters,
                            path=path,
                            cache=cache,
                            scope_parser=scope_parser,
                            logger=logger,
                            id_search_unsupported_resources=id_search_unsupported_resources,
                            add_cached_bundles_to_result=add_cached_bundles_to_result,
                        )
                        yield child_response
                        children.extend(child_response.get_bundle_entries())
                        parent_ids = []
                if parent_ids:
                    request_parameters = [f"{property_name}={','.join(parent_ids)}"] + additional_parameters
                    child_response = await self._process_child_group(
                        resource_type=target_type,
                        parent_ids=parent_ids,
                        parent_resource_type=parent_resource_type,
                        parameters=request_parameters,
                        path=path,
                        cache=cache,
                        scope_parser=scope_parser,
                        logger=logger,
                        id_search_unsupported_resources=id_search_unsupported_resources,
                        add_cached_bundles_to_result=add_cached_bundles_to_result,
                    )
                    yield child_response
                    children.extend(child_response.get_bundle_entries())
        if target.link:
            parent_link_map.append((target.link, children))

    async def _get_resources_by_id_one_by_one_async(
        self,
        *,
        resource_type: str,
        ids: list[str],
        cache: RequestCache,
        additional_parameters: list[str] | None,
        logger: Logger | None,
        compare_hash: bool = True,
    ) -> FhirGetResponse | None:
        result: FhirGetResponse | None = None
        non_cached_id_list: list[str] = []
        # first check to see if we can find these in the cache
        if ids:
            for resource_id in ids:
                cache_entry: RequestCacheEntry | None = await cache.get_async(
                    resource_type=resource_type, resource_id=resource_id
                )
                if cache_entry:
                    if logger:
                        logger.info(f"{cache_entry.status} Returning {resource_type}/{resource_id} from cache (1by1)")
                else:
                    if logger:
                        logger.info(f"Cache entry not found for {resource_type}/{resource_id} (1by1)")
                    non_cached_id_list.append(resource_id)

        for single_id in non_cached_id_list:
            result2: FhirGetResponse
            async for result2 in self._get_with_session_async(
                page_number=None,
                ids=[single_id],
                additional_parameters=additional_parameters,
                id_above=None,
                fn_handle_streaming_chunk=None,
                resource_type=resource_type,
            ):
                if result2.resource_type == "OperationOutcome":
                    result2 = FhirGetErrorResponse.from_response(other_response=result2)
                if result:
                    result = result.append(result2)
                else:
                    result = result2
                if result2.successful:
                    for entry in result2.get_bundle_entries():
                        cache_updated = await cache.add_async(
                            resource_type=resource_type,
                            resource_id=single_id,
                            bundle_entry=result2.get_bundle_entries()[0],
                            status=result2.status,
                            last_modified=result2.lastModified,
                            etag=result2.etag,
                            from_input_cache=False,
                            raw_hash=ResourceHash().hash_value(
                                json.dumps(json.loads(entry._resource.json()), sort_keys=True)
                            )
                            if compare_hash and entry._resource
                            else "",
                        )
                        if cache_updated and logger:
                            logger.info(f"Inserted {resource_type}/{single_id} into cache (1by1)")
                else:
                    cache_updated = await cache.add_async(
                        resource_type=resource_type,
                        resource_id=single_id,
                        bundle_entry=None,
                        status=result2.status,
                        last_modified=result2.lastModified,
                        etag=result2.etag,
                        from_input_cache=False,
                        raw_hash="",
                    )
                    if cache_updated and logger:
                        logger.info(f"Inserted {result2.status} for {resource_type}/{single_id} into cache (1by1)")

        return result

    async def _get_resources_by_parameters_async(
        self,
        *,
        id_: list[str] | str | None = None,
        resource_type: str,
        parameters: list[str] | None = None,
        cache: RequestCache,
        scope_parser: FhirScopeParser,
        logger: Logger | None,
        id_search_unsupported_resources: list[str],
        add_cached_bundles_to_result: bool = True,
        compare_hash: bool = True,
    ) -> tuple[FhirGetResponse, int]:
        assert resource_type
        if not scope_parser.scope_allows(resource_type=resource_type):
            if logger:
                logger.debug(f"Skipping resource {resource_type} due to scope")
            return (
                FhirGetResponseFactory.create(
                    request_id=None,
                    url="",
                    id_=None,
                    resource_type=resource_type,
                    response_text="",
                    response_headers=None,
                    status=200,
                    access_token=self._access_token,
                    next_url=None,
                    total_count=0,
                    extra_context_to_return=None,
                    error=None,
                    results_by_url=[],
                    storage_mode=self._storage_mode,
                    create_operation_outcome_for_error=self._create_operation_outcome_for_error,
                ),
                0,
            )

        id_list: list[str] | None
        if id_ and not isinstance(id_, list):
            id_list = [id_]
        else:
            id_list = cast(list[str] | None, id_)

        non_cached_id_list: list[str] = []
        # get any cached resources
        if id_list:
            for resource_id in id_list:
                cache_entry: RequestCacheEntry | None = await cache.get_async(
                    resource_type=resource_type, resource_id=resource_id
                )
                if cache_entry:
                    # if there is an entry then it means we tried to get it in the past
                    # so don't get it again whether we were successful or not
                    if logger:
                        logger.info(
                            f"{cache_entry.status} Returning {resource_type}/{resource_id} from cache (ByParam)"
                        )
                else:
                    if logger:
                        logger.info(f"Cache entry not found for {resource_type}/{resource_id} (ByParam)")
                    non_cached_id_list.append(resource_id)

        all_result: FhirGetResponse | None = None
        # either we have non-cached ids or this is a query without id but has other parameters
        if (
            (len(non_cached_id_list) > 1 and resource_type.lower() not in id_search_unsupported_resources)
            or len(non_cached_id_list) == 1
            or not id_
        ):
            # call the server to get the resources
            result1: FhirGetResponse
            result: FhirGetResponse | None
            async for result1 in self._get_with_session_async(
                page_number=None,
                ids=non_cached_id_list,
                additional_parameters=parameters,
                id_above=None,
                fn_handle_streaming_chunk=None,
                resource_type=resource_type,
            ):
                result = result1
                # if we got a failure then check if we can get it one by one
                if (not result or result.status != 200) and len(non_cached_id_list) > 1:
                    if result:
                        if resource_type.lower() not in id_search_unsupported_resources:
                            id_search_unsupported_resources.append(resource_type.lower())
                        if logger:
                            logger.info(
                                f"_id is not supported for resource_type={resource_type} for url {self._url}"
                                f" Fetching one by one ids: {non_cached_id_list}"
                            )
                    # For some resources if search by _id doesn't work then fetch one by one.
                    result = await self._get_resources_by_id_one_by_one_async(
                        resource_type=resource_type,
                        ids=non_cached_id_list,
                        additional_parameters=parameters,
                        cache=cache,
                        logger=logger,
                        compare_hash=compare_hash,
                    )
                else:
                    if logger:
                        logger.info(f"Fetched {resource_type} resources using _id for url {self._url}")
                if result:
                    if result.resource_type == "OperationOutcome":
                        result = FhirGetErrorResponse.from_response(other_response=result)

                    if not id_:
                        # remove entries that we have in the cache
                        await result.remove_entries_in_cache_async(
                            request_cache=cache, compare_hash=compare_hash, logger=logger
                        )

                    # append to the response
                    if all_result:
                        all_result = all_result.append(result)
                    else:
                        all_result = result
        # If non_cached_id_list is not empty and resource_type does not support ?_id search then fetch it one by one
        elif len(non_cached_id_list):
            all_result = await self._get_resources_by_id_one_by_one_async(
                resource_type=resource_type,
                ids=non_cached_id_list,
                additional_parameters=parameters,
                cache=cache,
                logger=logger,
                compare_hash=compare_hash,
            )

        # This list tracks the non-cached ids that were found
        found_non_cached_id_list: list[str] = []
        # Cache the fetched entries
        if all_result:
            non_cached_bundle_entry: FhirBundleEntry
            for non_cached_bundle_entry in all_result.get_bundle_entries():
                if non_cached_bundle_entry.resource:
                    non_cached_resource: FhirResource = non_cached_bundle_entry.resource
                    non_cached_resource_id: str | None = non_cached_resource.get("id")
                    if non_cached_resource_id:
                        cache_updated = await cache.add_async(
                            resource_type=resource_type,
                            resource_id=non_cached_resource_id,
                            bundle_entry=non_cached_bundle_entry,
                            status=(
                                int(non_cached_bundle_entry.response.status)
                                if non_cached_bundle_entry.response
                                else 200
                            ),
                            last_modified=(
                                non_cached_bundle_entry.response.lastModified
                                if non_cached_bundle_entry.response
                                else None
                            ),
                            etag=(non_cached_bundle_entry.response.etag if non_cached_bundle_entry.response else None),
                            from_input_cache=False,
                            raw_hash=ResourceHash().hash_value(
                                json.dumps(json.loads(non_cached_bundle_entry.resource.json()), sort_keys=True)
                            )
                            if compare_hash
                            else "",
                        )
                        if cache_updated and logger:
                            logger.debug(f"Inserted {resource_type}/{non_cached_resource_id} into cache (ByParam)")
                        found_non_cached_id_list.append(non_cached_resource_id)

        # now add all the non-cached ids that were NOT found to the cache too so we don't look for them again
        for non_cached_id in non_cached_id_list:
            if non_cached_id not in found_non_cached_id_list:
                cache_updated = await cache.add_async(
                    resource_type=resource_type,
                    resource_id=non_cached_id,
                    bundle_entry=None,
                    status=404,
                    last_modified=datetime.now(UTC),
                    etag=None,
                    from_input_cache=False,
                    raw_hash="",
                )
                if cache_updated and logger:
                    logger.info(f"Inserted 404 for {resource_type}/{non_cached_id} into cache (ByParam)")

        bundle_response: FhirGetBundleResponse = (
            FhirGetBundleResponse.from_response(other_response=all_result)
            if all_result
            else FhirGetBundleResponse.from_response(
                FhirGetErrorResponse(
                    request_id=None,
                    url="",
                    id_=non_cached_id_list,
                    resource_type=resource_type,
                    response_text="",
                    response_headers=None,
                    status=404,
                    access_token=self._access_token,
                    next_url=None,
                    total_count=0,
                    extra_context_to_return=None,
                    error=None,
                    results_by_url=[],
                    storage_mode=self._storage_mode,
                    create_operation_outcome_for_error=self._create_operation_outcome_for_error,
                )
            )
            if non_cached_id_list
            else FhirGetBundleResponse(
                request_id=None,
                url="",
                id_=None,
                resource_type=resource_type,
                response_text="",
                response_headers=None,
                status=200,
                access_token=self._access_token,
                next_url=None,
                total_count=0,
                extra_context_to_return=None,
                error=None,
                results_by_url=[],
                storage_mode=self._storage_mode,
            )
        )
        return bundle_response, cache.cache_hits

    # noinspection PyPep8Naming
    async def simulate_graph_async(
        self,
        *,
        id_: list[str] | str,
        graph_json: dict[str, Any],
        contained: bool,
        separate_bundle_resources: bool = False,
        restrict_to_scope: str | None = None,
        restrict_to_resources: list[str] | None = None,
        restrict_to_capability_statement: str | None = None,
        retrieve_and_restrict_to_capability_statement: bool | None = None,
        ifModifiedSince: datetime | None = None,
        eTag: str | None = None,
        request_size: int | None = 1,
        max_concurrent_tasks: int | None = 1,
        sort_resources: bool | None = False,
        add_cached_bundles_to_result: bool = True,
        input_cache: RequestCache | None = None,
        compare_hash: bool = True,
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
        :param request_size: Optional Count of resources to request in one request
        :param max_concurrent_tasks: Optional number of concurrent tasks.  If 1 then the tasks are processed sequentially.
        :param sort_resources: Optional flag to sort resources
        :param add_cached_bundles_to_result: Optional flag to add cached bundles to result
        :param input_cache: Optional cache to use for input
        :param compare_hash: Optional flag to compare hash of the resources
        :return: FhirGetResponse
        """
        if contained:
            if not self._additional_parameters:
                self.additional_parameters([])
            assert self._additional_parameters is not None
            self._additional_parameters.append("contained=true")

        result: FhirGetResponse | None = await FhirGetResponse.from_async_generator(
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
                add_cached_bundles_to_result=add_cached_bundles_to_result,
                input_cache=input_cache,
                compare_hash=compare_hash,
            )
        )
        assert result, "No result returned from simulate_graph_async"
        return result

    # noinspection PyPep8Naming
    async def simulate_graph_streaming_async(
        self,
        *,
        id_: list[str] | str,
        graph_json: dict[str, Any],
        contained: bool,
        separate_bundle_resources: bool = False,
        restrict_to_scope: str | None = None,
        restrict_to_resources: list[str] | None = None,
        restrict_to_capability_statement: str | None = None,
        retrieve_and_restrict_to_capability_statement: bool | None = None,
        ifModifiedSince: datetime | None = None,
        eTag: str | None = None,
        request_size: int | None = 1,
        max_concurrent_tasks: int | None = 1,
        sort_resources: bool | None = False,
        input_cache: RequestCache | None = None,
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
        :param request_size: Optional Count of resources to request in one request
        :param max_concurrent_tasks: Optional number of concurrent tasks.  If 1 then the tasks are processed sequentially
        :param sort_resources: Optional flag to sort resources
        :param input_cache: Optional cache to use for input
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
            input_cache=input_cache,
        ):
            yield r
