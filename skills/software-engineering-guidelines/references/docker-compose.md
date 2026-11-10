# Docker Compose environment variables

When creating or modifying Docker Compose files:

- MUST use braced variable interpolation (`${VAR}`) for externally supplied values. Declare container environment variables explicitly under `environment`, for example `LOG_LEVEL: ${LOG_LEVEL}`. MUST NOT use the service-level `env_file` attribute.
- MUST use `${VAR:?VAR must be set}` for every required variable, for example `DATABASE_URL: ${DATABASE_URL:?DATABASE_URL must be set}`. Required variables must reject both unset and empty values. MUST NOT supply fallback defaults for required variables.
- Supply interpolation values through the shell environment, Compose's default `.env`, or the CLI `--env-file` option. These are interpolation sources, distinct from the prohibited service-level `env_file` attribute. Keep actual secrets out of version control and list required variable names in `.env.example` without real credentials.
- Before delivery, validate with `docker compose config --quiet` using the same files and interpolation sources as the startup command. Verify that valid values pass and each required variable fails when unset or empty. Do not print or retain resolved configuration containing secrets.
