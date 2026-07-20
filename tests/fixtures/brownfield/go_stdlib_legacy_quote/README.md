# Legacy Go quote-order fixture

This deliberately small brownfield application exposes one real
`POST /quote-order` HTTP behavior through Go's standard-library `net/http`
router. Its exported helper functions intentionally create plausible but false
behavior candidates so onboarding must preserve provenance and require
explicit review.

The application uses Go 1.26.5. The server listens on `127.0.0.1:8080` by
default. A caller may pass `--listen=127.0.0.1:0` to request an ephemeral
loopback port; the sole stdout line is then `READY http://<address>`. SIGINT
and SIGTERM trigger a bounded graceful shutdown.

UCF treats this directory as immutable legacy input. Native builds, tests, and
adapter verification run from external copies and must leave every regular
input byte-identical.
