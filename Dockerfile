ARG BASE_IMAGE="python:3.13.0"

FROM ${BASE_IMAGE} AS base

ENV HOME_PATH="/shortify"
ENV PATH="${HOME_PATH}/.venv/bin:${PATH}"

WORKDIR ${HOME_PATH}

FROM base AS deps

RUN pip install --no-cache-dir --upgrade pip \
&& pip install --no-cache-dir --upgrade uv==0.9.21

COPY pyproject.toml uv.lock ${HOME_PATH}/
RUN uv sync --frozen --no-install-project --no-dev

FROM deps AS development

COPY --from=deps ${HOME_PATH}/.venv ${HOME_PATH}/.venv
COPY shortify ${HOME_PATH}/shortify
WORKDIR ${HOME_PATH}

EXPOSE 8000

ENTRYPOINT ["uvicorn", "shortify.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips='*'"]
