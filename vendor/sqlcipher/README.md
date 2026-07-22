# Controlled SQLCipher runtime

`PROVENANCE.json` is the release authority for the bundled CPython 3.14 Windows
x64 database driver. The matching wheel is committed beside it and resolved
directly through `pyproject.toml` and `uv.lock`. Normal CI verifies its SHA-256,
native extension inventory, SQLCipher version, crypto provider, required compile
options, encrypted canary database, and frozen executable runtime.

`.github/workflows/build-sqlcipher-wheel.yml` is a manually dispatched candidate
builder. It checks the pinned source identities, generates the SQLCipher
amalgamation, builds OpenSSL and the binding, and probes the candidate. Candidate
builds are not expected to be byte-for-byte identical across compiler updates.
A candidate replaces the bundled wheel only after its measured hash and native
inventory are recorded here, reviewed, committed, and accepted by the normal
release gates.
