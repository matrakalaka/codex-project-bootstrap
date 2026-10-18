# Local staging deployment

The staging service is loopback-only and must not be exposed beyond the host.
Use `scripts/qualify_agentterm_host.sh` to run the integrated acceptance flow.

Production requires an HTTPS termination layer, OS-backed secrets, a reviewed
multi-instance database adapter, provider credentials, monitoring, retention,
and independent approval. The example environment intentionally cannot enable
production Git mutation and is not a production configuration.
