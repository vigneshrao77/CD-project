"""
Flask web UI for the cppjava C++ -> Java compiler.
Supports both interactive terminal execution and batch STDIN.
Run:  python ui/app.py
Open: http://127.0.0.1:5000
"""
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request

# Project root on sys.path so `cppjava` is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cppjava.compiler import compile_source
from cppjava.diagnostics import CompileError

app = Flask(__name__)

def _find_tool(name: str) -> str:
    path = shutil.which(name)
    return path or name

JAVAC = _find_tool("javac")
JAVA  = _find_tool("java")

# ── Interactive process sessions ──────────────────────────────────
class ActiveSession:
    def __init__(self, tmpdir: tempfile.TemporaryDirectory, class_name: str):
        self.tmpdir = tmpdir
        self.class_name = class_name
        self.proc: subprocess.Popen | None = None
        self.out_q = queue.Queue()
        self.err_q = queue.Queue()
        self.t_out = None
        self.t_err = None
        self.start_time = 0
        self.closed = False

    def start(self):
        self.start_time = time.monotonic()
        self.proc = subprocess.Popen(
            [JAVA, self.class_name],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.tmpdir.name,
            bufsize=0
        )

        def read_stream(stream, q):
            while True:
                try:
                    chunk = stream.read(1024)
                    if not chunk:
                        break
                    q.put(chunk)
                except Exception:
                    break

        self.t_out = threading.Thread(target=read_stream, args=(self.proc.stdout, self.out_q), daemon=True)
        self.t_err = threading.Thread(target=read_stream, args=(self.proc.stderr, self.err_q), daemon=True)
        self.t_out.start()
        self.t_err.start()

    def get_output(self, wait_sec=0.25):
        if wait_sec > 0:
            time.sleep(wait_sec)
        out = b""
        while not self.out_q.empty():
            out += self.out_q.get()
        err = b""
        while not self.err_q.empty():
            err += self.err_q.get()
        return out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace")

    def send_input(self, text: str):
        if self.proc and self.proc.stdin and self.proc.poll() is None:
            self.proc.stdin.write(text.encode("utf-8") + b"\n")
            self.proc.stdin.flush()

    def is_done(self) -> bool:
        return self.proc is None or self.proc.poll() is not None

    def exit_code(self):
        return self.proc.poll() if self.proc else None

    def elapsed_ms(self) -> int:
        return round((time.monotonic() - self.start_time) * 1000)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.kill()
        except Exception:
            pass
        try:
            self.tmpdir.cleanup()
        except Exception:
            pass

SESSIONS: dict[str, ActiveSession] = {}

def cleanup_stale_sessions():
    now = time.monotonic()
    stale_keys = []
    for k, s in list(SESSIONS.items()):
        if s.closed or (now - s.start_time > 120):
            stale_keys.append(k)
    for k in stale_keys:
        s = SESSIONS.pop(k, None)
        if s:
            s.close()


# ── Routes ────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/convert", methods=["POST"])
def convert():
    data       = request.get_json(force=True)
    source     = data.get("source", "")
    class_name = (data.get("class_name") or "Main").strip()

    if not class_name.isidentifier():
        return jsonify({"success": False, "errors": [{
            "phase": "driver", "code": "invalid", "line": 1, "column": 1,
            "message": f"'{class_name}' is not a valid Java class name."
        }]})

    try:
        result = compile_source(source, class_name)
        return jsonify({
            "success": True,
            "java": result.java,
            "phases": {
                "tokens":              result.dump("tokens"),
                "preprocessed_tokens": result.dump("preprocessed_tokens"),
                "ast":                 result.dump("ast"),
                "annotated_ast":       result.dump("annotated_ast"),
                "ir":                  result.dump("ir"),
            }
        })
    except CompileError as e:
        return jsonify({"success": False, "errors": [d.to_dict() for d in e.diagnostics]})
    except Exception as e:
        return jsonify({"success": False, "errors": [{
            "phase": "internal", "code": "exception", "line": 1, "column": 1,
            "message": str(e)
        }]})


@app.route("/api/run/start", methods=["POST"])
def run_start():
    cleanup_stale_sessions()
    data       = request.get_json(force=True)
    java_src   = data.get("java", "")
    class_name = (data.get("class_name") or "Main").strip() or "Main"

    if not java_src.strip():
        return jsonify({"success": False, "compile_stderr": "No Java source provided."})

    tmpdir = tempfile.TemporaryDirectory()
    src_file = Path(tmpdir.name) / f"{class_name}.java"
    src_file.write_text(java_src, encoding="utf-8")

    # Compile with javac
    t0 = time.monotonic()
    try:
        javac_proc = subprocess.run(
            [JAVAC, "-encoding", "UTF-8", str(src_file)],
            capture_output=True, text=True, timeout=30, cwd=tmpdir.name
        )
    except FileNotFoundError:
        tmpdir.cleanup()
        return jsonify({"success": False, "compile_stderr": "javac not found. Install JDK 17+ and add to PATH."})
    except subprocess.TimeoutExpired:
        tmpdir.cleanup()
        return jsonify({"success": False, "compile_stderr": "javac timed out (30s)."})

    if javac_proc.returncode != 0:
        err = javac_proc.stderr.replace(str(tmpdir.name) + os.sep, "").strip()
        tmpdir.cleanup()
        return jsonify({"success": False, "compile_stderr": err, "exit_code": javac_proc.returncode})

    # Start session
    sess = ActiveSession(tmpdir, class_name)
    sess.start()
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = sess

    # Capture initial output (e.g. prompts like "Enter a non-negative integer: ")
    stdout, stderr = sess.get_output(wait_sec=0.3)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "stdout": stdout,
        "stderr": stderr,
        "is_done": sess.is_done(),
        "exit_code": sess.exit_code(),
        "elapsed_ms": sess.elapsed_ms()
    })


@app.route("/api/run/input", methods=["POST"])
def run_input():
    data = request.get_json(force=True)
    session_id = data.get("session_id", "")
    input_text = data.get("input", "")

    sess = SESSIONS.get(session_id)
    if not sess:
        return jsonify({"success": False, "error": "Session expired or not found."})

    sess.send_input(input_text)
    stdout, stderr = sess.get_output(wait_sec=0.25)

    is_done = sess.is_done()
    exit_code = sess.exit_code()
    elapsed = sess.elapsed_ms()

    if is_done:
        sess.close()
        SESSIONS.pop(session_id, None)

    return jsonify({
        "success": True,
        "stdout": stdout,
        "stderr": stderr,
        "is_done": is_done,
        "exit_code": exit_code,
        "elapsed_ms": elapsed
    })


@app.route("/api/run/stop", methods=["POST"])
def run_stop():
    data = request.get_json(force=True)
    session_id = data.get("session_id", "")
    sess = SESSIONS.pop(session_id, None)
    if sess:
        sess.close()
    return jsonify({"success": True})


@app.route("/api/examples")
def examples():
    corpus = ROOT / "tests" / "corpus"
    result = []
    if corpus.exists():
        for f in sorted(corpus.glob("*.cpp")):
            try:
                result.append({"name": f.stem, "source": f.read_text(encoding="utf-8-sig")})
            except Exception:
                pass
    return jsonify(result)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 58)
    print("  cppjava UI  --  C++ to Java Compiler")
    print("  http://127.0.0.1:5000")
    print("=" * 58)
    app.run(debug=True, port=5000)
