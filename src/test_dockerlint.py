from dockerlint import lint
GOOD = """FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -r app
USER app
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health')"
CMD ["python", "main.py"]
"""
def has(p, s): return any(s in x for x in p)
def test_good(): assert lint(GOOD) == []
def test_latest_tag(): assert has(lint(GOOD.replace("python:3.12-slim", "python:latest")), "':latest'")
def test_no_tag(): assert has(lint(GOOD.replace("python:3.12-slim", "python")), "missing")
def test_digest_ok(): assert not has(lint(GOOD.replace("python:3.12-slim", "python@sha256:" + "a" * 64)), "tag")
def test_root(): assert has(lint(GOOD.replace("USER app", "")), "runs as root")
def test_shell_form_cmd(): assert has(lint(GOOD.replace('["python", "main.py"]', "python main.py")), "exec form")
def test_apt_cleanup():
    bad = GOOD.replace("RUN useradd -r app", "RUN apt-get update && apt-get install -y curl\nRUN useradd -r app")
    p = lint(bad); assert has(p, "--no-install-recommends") and has(p, "apt lists not removed")
def test_apt_ok():
    ok = GOOD.replace("RUN useradd -r app", "RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* && useradd -r app")
    assert lint(ok) == []
def test_secret(): assert has(lint(GOOD.replace("WORKDIR /app", "ENV API_TOKEN=abc123\nWORKDIR /app")), "secret")
def test_add_vs_copy(): assert has(lint(GOOD.replace("COPY . .", "ADD . .")), "COPY instead of ADD")
def test_curl_pipe_sh(): assert has(lint(GOOD.replace("WORKDIR /app", "RUN curl -fsSL https://example.com/install.sh | sh\nWORKDIR /app")), "pipes a download")
def test_multistage_checks_final_stage():
    ms = "FROM golang:1.22 AS build\nRUN go build -o /app\nFROM gcr.io/distroless/static:nonroot\nCOPY --from=build /app /app\nUSER nonroot\nHEALTHCHECK NONE\nENTRYPOINT [\"/app\"]\n"
    assert lint(ms) == []
