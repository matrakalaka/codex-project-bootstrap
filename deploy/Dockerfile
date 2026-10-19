FROM python:3.12-slim

WORKDIR /opt/agentterm
COPY vendor/agentterm /opt/agentterm/vendor/agentterm
COPY scripts/run_agentterm_postgres_service.py /opt/agentterm/scripts/run_agentterm_postgres_service.py
RUN python -m pip install --no-cache-dir '/opt/agentterm/vendor/agentterm[hosted]'

USER 65532:65532
EXPOSE 8765
ENTRYPOINT ["python", "/opt/agentterm/scripts/run_agentterm_postgres_service.py"]
