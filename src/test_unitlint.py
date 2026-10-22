from unitlint import lint

GOOD = """[Unit]
Description=Example API
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=myapp
ExecStart=/opt/myapp/bin/server --port 8080
Restart=on-failure
RestartSec=2s
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/var/lib/myapp

[Install]
WantedBy=multi-user.target
"""

def has(problems, needle): return any(needle in p for p in problems)

def test_good_unit_is_clean(): assert lint(GOOD) == []
def test_relative_exec(): assert has(lint(GOOD.replace("/opt/myapp/bin/server", "server")), "absolute path")
def test_shell_syntax(): assert has(lint(GOOD.replace("--port 8080", "--port 8080 > /var/log/x.log")), "shell syntax")
def test_runs_as_root(): assert has(lint(GOOD.replace("User=myapp\n", "")), "runs as root")
def test_dynamic_user_ok(): assert not has(lint(GOOD.replace("User=myapp", "DynamicUser=yes")), "runs as root")
def test_no_install(): assert has(lint(GOOD.replace("WantedBy=multi-user.target", "")), "enable")
def test_missing_restart(): assert has(lint(GOOD.replace("Restart=on-failure\n", "")), "Restart=")
def test_always_without_sec():
    u = GOOD.replace("Restart=on-failure", "Restart=always").replace("RestartSec=2s\n", "")
    assert has(lint(u), "RestartSec")
def test_forking_pidfile(): assert has(lint(GOOD.replace("Type=exec", "Type=forking")), "PIDFile")
def test_oneshot_without_exec_ok():
    u = "[Unit]\nDescription=x\n[Service]\nType=oneshot\nUser=x\nNoNewPrivileges=yes\nPrivateTmp=yes\n[Install]\nWantedBy=multi-user.target\n"
    assert not has(lint(u), "ExecStart")
def test_sandboxing_hint(): assert has(lint("[Unit]\nDescription=x\n[Service]\nUser=a\nExecStart=/bin/true\nRestart=no\n[Install]\nWantedBy=multi-user.target\n"), "sandboxing")
