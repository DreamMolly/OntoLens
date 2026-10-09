ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}
ARG PIP_INDEX_URL=https://pypi.org/simple
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PEIWU_ROOT=/app PEIWU_DB=/state/workbench.sqlite3 PEIWU_WORKSPACE_MODE=operational PEIWU_AUTH_FILE=/config/accounts.json PEIWU_SESSION_DB=/state/access.sqlite3
COPY pyproject.toml ./
RUN python -c "import subprocess, sys, tomllib; p = tomllib.load(open('pyproject.toml', 'rb'))['project']; deps = p['dependencies'] + p['optional-dependencies']['workbench'] + p['optional-dependencies']['jev']; subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', 'setuptools', 'wheel', *deps])"
COPY README.md ./
COPY src ./src
COPY data ./data
RUN pip install --no-cache-dir --no-deps --no-build-isolation . && useradd --uid 10001 --create-home ontolens && mkdir /state /config && chown ontolens:ontolens /state /config
USER ontolens
EXPOSE 8768
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8768/api/auth/session', timeout=3)"
CMD ["python", "-m", "uvicorn", "peiwu.web:create_app", "--factory", "--host", "0.0.0.0", "--port", "8768", "--no-proxy-headers"]
