"""Capture-time emission: the minimum record an agent or a lab system writes at the end of a run.

`profile` defines and checks the minimum. `robin` and `datahub` are emitters for two open systems: a run folder from
FutureHouse's Robin agent, and an instrument run from Arcadia's Data Hub. Both produce ordinary NRR v0.2 records
that pass `nrr.schema.validate`; the profile adds what capture must not leave out.
"""
