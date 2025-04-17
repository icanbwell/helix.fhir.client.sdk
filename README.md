# helix.fhir.client.sdk

<p align="left">
  <a href="https://github.com/icanbwell/helix.fhir.client.sdk/actions">
    <img src="https://github.com/icanbwell/helix.fhir.client.sdk/workflows/Build%20and%20Test/badge.svg"
         alt="Continuous Integration">
  </a>
  <a href="https://github.com/icanbwell/helix.fhir.client.sdk/releases/latest">
    <img src="https://img.shields.io/github/v/release/icanbwell/helix.fhir.client.sdk?display_name=tag"
          alt="Latest Release">
  </a>
  <a href="https://github.com/icanbwell/helix.fhir.client.sdk/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202-blue"
         alt="GitHub license">
  </a>
</p>

Fluent API to call the FHIR server that handles:

1. Authentication to FHIR server
2. Renewing access token when they expire
3. Retry when there are transient errors
4. Un-bundling the resources received from FHIR server
5. Paging
6. Streaming
7. Logging
8. Simulating a $graph call when the server does not support it


# Usage
`pip install helix.fhir.client.sdk`

# Documentation
https://icanbwell.github.io/helix.fhir.client.sdk/

# Test Project using this
https://github.com/icanbwell/fhir-server-performance

# Python Version Support
* 1.x supports python 3.7+ 
* 2.x supports python 3.10+
* 3.x supports python 3.12+

# Asynchronous Support
When communicating with FHIR servers, a lot of time is spent waiting for the server to respond. 
This is a good use case for using asynchronous programming. 
This SDK supports asynchronous programming using the `async` and `await` keywords.

The return types are Python AsyncGenerators.  Python makes it very easy to work with AsyncGenerators.

For example, if the SDK provides a function like this:
```python

async def get_resources(self) -> AsyncGenerator[FhirGetResponse, None]:
    ...
```

You can iterate over the results as they become available:
```python
response: Optional[FhirGetResponse]
async for response in client.get_resources():
    print(response.resource)
```

Or you can get a list of responses (which will return AFTER all the responses are received:
```python

responses: List[FhirGetResponse] = [response async for response in client.get_resources()]
```

Or you can aggregate the responses into one response (which will return AFTER all the responses are received:
```python

response: Optional[FhirGetResponse] = await FhirGetResponse.from_async_generator(client.get_resources())
```

# Data Streaming
For FHIR servers that support data streaming (e.g., b.well FHIR server), you can just set the `use_data_streaming` parameter to stream the data as it i received.
The data will be streamed in AsyncGenerators as described above.

# Storage Compression
The FHIR client SDK natively stores the FHIR resources compressed in memory.  This allows use in environments where you are processing large number of FHIR resources.

# FhirAuthMixin
The `FhirAuthMixin` class handles authentication and token renewal.

## Example usage of FhirAuthMixin
```python
from helix_fhir_client_sdk.fhir_client import FhirClient

client = FhirClient()
client.url("https://fhirserver.com")
client.client_credentials(client_id="your_client_id", client_secret="your_client_secret")
client.auth_scopes(["system/AllergyIntolerance.read"])
client.auth_wellknown_url("https://fhirserver.com/.well-known/smart-configuration")
```

# FhirBundleAppender
The `FhirBundleAppender` class appends responses to a bundle.

## Example usage of FhirBundleAppender
```python
from helix_fhir_client_sdk.fhir_bundle_appender import FhirBundleAppender
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import CompressedDictStorageMode

responses = [FhirGetResponse(...), FhirGetResponse(...)]
bundle = FhirBundle(...)
storage_mode = CompressedDictStorageMode(storage_type="raw")

appender = FhirBundleAppender()
updated_bundle = appender.append_responses(responses=responses, bundle=bundle, storage_mode=storage_mode)
```

# FhirClient
The `FhirClient` class is the main class used to call the FHIR server.

## Example usage of FhirClient
```python
from helix_fhir_client_sdk.fhir_client import FhirClient

client = FhirClient()
client.url("https://fhirserver.com")
client.resource("Patient")
client.id_("123")
response = client.get()
print(response.resource)
```

# FhirDeleteMixin
The `FhirDeleteMixin` class handles deletion of resources.

## Example usage of FhirDeleteMixin
```python
from helix_fhir_client_sdk.fhir_client import FhirClient

client = FhirClient()
client.url("https://fhirserver.com")
client.resource("Patient")
client.id_("123")
response = client.delete()
print(response.status)
```

# FhirGraphMixin
The `FhirGraphMixin` class handles graph queries.

## Example usage of FhirGraphMixin
```python
from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.graph.graph_definition import GraphDefinition

client = FhirClient()
client.url("https://fhirserver.com")
graph_definition = GraphDefinition(start="Patient", link=[...])
response = client.graph(graph_definition=graph_definition, contained=True)
print(response.resource)
```

# FhirMergeMixin
The `FhirMergeMixin` class handles merging of resources.

## Example usage of FhirMergeMixin
```python
from helix_fhir_client_sdk.fhir_client import FhirClient

client = FhirClient()
client.url("https://fhirserver.com")
client.resource("Patient")
client.id_("123")
client.action("merge")
response = client.get()
print(response.resource)
```

# FhirUpdateMixin
The `FhirUpdateMixin` class handles updating of resources.

## Example usage of FhirUpdateMixin
```python
from helix_fhir_client_sdk.fhir_client import FhirClient

client = FhirClient()
client.url("https://fhirserver.com")
client.resource("Patient")
client.id_("123")
client.action("update")
response = client.get()
print(response.resource)
```

# RetryableAioHttpClient
The `RetryableAioHttpClient` class provides a way to make HTTP calls with automatic retry and token refreshing.

## Example usage of RetryableAioHttpClient
```python
from helix_fhir_client_sdk.utilities.retryable_aiohttp_client import RetryableAioHttpClient

async def fetch_data():
    async with RetryableAioHttpClient(fn_get_session=lambda: create_http_session()) as client:
        response = await client.get(url="https://fhirserver.com/Patient/123")
        print(await response.get_text_async())

import asyncio
asyncio.run(fetch_data())
```
