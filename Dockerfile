FROM python:3.12-alpine
RUN apk add --no-cache git bash
WORKDIR /opt/questops
COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv
RUN uv pip install --system --no-cache .
ENV QUESTOPS_DATA_DIR=/data
ENTRYPOINT ["questops"]
CMD ["quest", "--dry-run", "--outcome", "success"]
