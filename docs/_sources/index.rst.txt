.. Helix Project documentation master file, created by
   sphinx-quickstart on Thu Mar 25 11:58:19 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

helix.fhir.client.sdk
=====================
Fluent API to call the FHIR server that handles:

1. Authentication to FHIR server
2. Renewing access token when they expire
3. Retry when there are transient errors
4. Un-bundling the resources received from FHIR server

Main EntryPoint is :class:`~helix_fhir_client_sdk.fhir_client.FhirClient`.

`Github Repo <https://github.com/icanbwell/helix.fhir.client.sdk>`_

Example
========

.. code-block:: python

   server_url = "https://fhir.icanbwell.com/4_0_0"
   auth_client_id = "{put client_id here}"
   auth_client_secret = "{put client_secret here}"
   auth_scopes = ["user/*.read", "access/*.*"]
   fhir_client: FhirClient = FhirClient()
   fhir_client = fhir_client.url(server_url)
   fhir_client = fhir_client.resource("Patient")
   fhir_client = fhir_client.client_credentials(auth_client_id, auth_client_secret)
   fhir_client = fhir_client.auth_scopes(auth_scopes)

   # Optional
   fhir_client = fhir_client.page_size(page_size).page_number(page_number)

   fhir_client = fhir_client.sort_fields(sort_fields)

   fhir_client = fhir_client.additional_parameters(additional_parameters)

   fhir_client = fhir_client.last_updated_before(last_updated_before)

   fhir_client = fhir_client.last_updated_after(last_updated_after)

   result = fhir_client.get()

   import json
   resource_list = json.loads(result.responses)
   for resource in resource_list:
      print(resource.id)

Contents:
==================
.. toctree::
   :maxdepth: 6
   :titlesonly:


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
