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

   fhir_client: FhirClient = FhirClient()
   fhir_client = fhir_client.url(server_url)
   if auth_server_url:
       fhir_client = fhir_client.auth_server_url(auth_server_url)
   if auth_client_id and auth_client_secret:
       fhir_client = fhir_client.client_credentials(auth_client_id, auth_client_secret)
   if auth_login_token:
       fhir_client = fhir_client.login_token(auth_login_token)
   if auth_scopes:
       fhir_client = fhir_client.auth_scopes(auth_scopes)
   if include_only_properties:
       fhir_client = fhir_client.include_only_properties(
           include_only_properties=include_only_properties
       )
   if page_size and page_number is not None:
       fhir_client = fhir_client.page_size(page_size).page_number(page_number)
   if sort_fields is not None:
       fhir_client = fhir_client.sort_fields(sort_fields)
   if additional_parameters:
       fhir_client = fhir_client.additional_parameters(additional_parameters)

   # have to done here since this arg can be used twice
   if last_updated_before:
       fhir_client = fhir_client.last_updated_before(last_updated_before)
   if last_updated_after:
       fhir_client = fhir_client.last_updated_after(last_updated_after)

   result = fhir_client.get()


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
