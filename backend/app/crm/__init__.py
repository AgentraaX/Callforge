"""CRM: persistent contacts, companies, deals, activities and call history.

Additive Postgres layer (see ``app/db``). The voice pipeline, auth and
personas are untouched -- when a call ends, ``ingest.persist_call`` mirrors
it into this store; everything else is driven by ``routes`` under
``/api/crm``.
"""
