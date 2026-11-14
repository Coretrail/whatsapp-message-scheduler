FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --ignore-scripts
COPY frontend/index.html ./
COPY frontend/src ./src
COPY frontend/public ./public
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 FRONTEND_DIST=/app/frontend/dist
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 scheduler \
    && useradd --uid 10001 --gid scheduler --no-create-home scheduler \
    && mkdir -p /data && chown scheduler:scheduler /data
COPY --chown=scheduler:scheduler LICENSE THIRD_PARTY_NOTICES.md ./
COPY --chown=scheduler:scheduler docs/licenses ./docs/licenses
COPY --chown=scheduler:scheduler scheduler ./scheduler
COPY --from=frontend --chown=scheduler:scheduler /build/dist ./frontend/dist
USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "scheduler.api:production_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--no-proxy-headers"]

FROM runtime AS test
USER root
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM runtime AS release
