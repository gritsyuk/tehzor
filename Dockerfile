# syntax=docker/dockerfile:1
# MCP-сервер Tehzor.
#   docker build -t tehzor-mcp .
#   за корпоративным прокси с собственным CA (сертификат в образ не попадает):
#     docker build --build-arg HTTPS_PROXY --secret id=pip_ca,src=/path/to/ca.pem -t tehzor-mcp .
#   stdio (Claude Desktop / Claude Code):  docker run -i --rm -e TEHZOR_API_KEY tehzor-mcp
#   HTTP:  docker run --rm -p 8000:8000 -e TEHZOR_API_KEY -e TEHZOR_MCP_HTTP_TOKEN tehzor-mcp --transport http
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE.txt ./
COPY tehzor ./tehzor
RUN --mount=type=secret,id=pip_ca,required=false \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    pip install --no-cache-dir build && python -m build --wheel --outdir /dist

FROM python:3.12-slim
LABEL org.opencontainers.image.title="tehzor-mcp" \
      org.opencontainers.image.description="MCP-сервер Tehzor Public API для LLM-агентов" \
      org.opencontainers.image.source="https://github.com/gritsyuk/tehzor" \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TEHZOR_MCP_HOST=0.0.0.0 \
    TEHZOR_MCP_AUDIT_LOG=/data/audit.jsonl
COPY --from=build /dist/*.whl /tmp/
RUN --mount=type=secret,id=pip_ca,required=false \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    pip install "$(ls /tmp/*.whl)[mcp]" && rm /tmp/*.whl \
    && useradd --create-home --uid 10001 tehzor && mkdir /data && chown tehzor /data
USER tehzor
VOLUME ["/data"]
EXPOSE 8000
ENTRYPOINT ["tehzor-mcp"]
