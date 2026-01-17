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
For FHIR servers that support data streaming (e.g., b.well FHIR server), you can just set the `use_data_streaming` parameter to stream the data as it is received.
The data will be streamed in AsyncGenerators as described above.

# Persistent Sessions (Connection Reuse)
By default, the SDK creates a new HTTP session for each request. For better performance (~4× faster), 
you can use persistent sessions to reuse connections across multiple requests.

**Important**: When you provide a custom session factory using `use_http_session()`, YOU are responsible 
for managing the session lifecycle, including closing it when done. The SDK will NOT automatically close 
user-provided sessions.

```python
import aiohttp
from helix_fhir_client_sdk.fhir_client import FhirClient

# Create a persistent session for connection reuse
session = aiohttp.ClientSession()

try:
    # Configure FhirClient to use persistent session
    fhir_client = (
        FhirClient()
        .url("https://fhir.example.com")
        .resource("Patient")
        .use_http_session(lambda: session)  # User provides session factory
    )
    
    # Multiple requests reuse the same connection (~4× performance boost)
    response1 = await fhir_client.get_async()
    response2 = await fhir_client.clone().resource("Observation").get_async()
    
finally:
    # User must close the session when done
    await session.close()
```

**Session Lifecycle Rules**:
- **No custom factory** (default): SDK creates and closes the session automatically
- **Custom factory provided**: User is responsible for closing the session

# Storage Compression
The FHIR client SDK supports two types of compression:

1. **HTTP Compression** (`compress`): Compresses HTTP request body when sending data to the server. Default: **enabled**
2. **In-Memory Storage** (`storage_mode`): Controls how FHIR resources are stored in memory. Default: **raw (no compression)**

## Disabling HTTP Compression
HTTP compression (gzip) is enabled by default for request bodies. To disable it:

```python
from helix_fhir_client_sdk.fhir_client import FhirClient

# Disable HTTP compression for requests
fhir_client = FhirClient().url("https://fhir.example.com").compress(False)
```

## In-Memory Storage Modes
The SDK supports different storage modes for FHIR resources through the `set_storage_mode()` method.
By default, resources are stored as raw Python dictionaries (no compression).

```python
from helix_fhir_client_sdk.fhir_client import FhirClient
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import CompressedDictStorageMode

# Use raw storage (default) - no compression, resources stored as plain Python dicts
fhir_client = FhirClient().set_storage_mode(CompressedDictStorageMode(storage_type="raw"))

# Use msgpack storage - stores resources in msgpack format
fhir_client = FhirClient().set_storage_mode(CompressedDictStorageMode(storage_type="msgpack"))

# Use compressed msgpack storage - stores resources in compressed msgpack format
fhir_client = FhirClient().set_storage_mode(CompressedDictStorageMode(storage_type="compressed_msgpack"))
```

Available storage types:
- `raw`: Default. Resources are stored as standard Python dictionaries (no compression)
- `msgpack`: Resources are serialized using MessagePack for efficient storage
- `compressed_msgpack`: Resources are serialized using MessagePack and then compressed

## Getting Raw Python Dictionaries
To completely bypass the `compressedfhir` library and get plain Python dictionaries:

```python
# Returns plain Python dicts, not FhirResource objects
result = await fhir_client.get_raw_resources_async()
resources = result["_resources"]  # list[dict[str, Any]]
```
