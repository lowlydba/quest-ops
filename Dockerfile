FROM python:3.12-alpine
RUN apk add --no-cache git bash
WORKDIR /opt/questops
COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
RUN pip install --no-cache-dir .
ENV QUESTOPS_DATA_DIR=/data
ENTRYPOINT ["questops"]
CMD ["quest", "--dry-run", "--outcome", "success"]
