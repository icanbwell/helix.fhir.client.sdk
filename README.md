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
1.x supports python 3.7+
2.x supports python 3.10+
