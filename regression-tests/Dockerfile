FROM python:3.11.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/task
COPY requirements-task.lock /opt/requirements-task.lock
RUN pip install --no-cache-dir --require-hashes -r /opt/requirements-task.lock
RUN useradd --uid 10001 --create-home worker && mkdir /task && chown worker:worker /task
WORKDIR /task
USER 10001:10001