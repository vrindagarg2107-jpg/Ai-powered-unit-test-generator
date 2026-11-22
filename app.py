import os, re, json, subprocess, tempfile, sys, ast
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

SYSTEM_PROMPTS = {
"v1": """You are an AI unit test generator. Analyze the supplied source code and create executable unit tests in the requested framework. Cover normal, boundary, and invalid inputs. Do not invent behavior. Return JSON with keys: summary, functions, test_code, cases. Each case has name, category, input, expected, rationale.""",
"v2": """Act as a senior software test engineer. First inspect the actual source code: identify callable functions, parameters, return values, branches, exceptions, and dependencies. Generate tests only for behavior supported by the code. Include normal, boundary, negative, empty, and invalid cases where relevant. Use the exact requested framework. Return valid JSON with summary, functions, test_code, cases. Each case must include name, category, input, expected, rationale. Explicitly flag assumptions.""",
"v3": """You are an expert QA engineer. Carefully analyze the source code and produce a reliable unit-test suite in the specified language/framework. Requirements: (1) never fabricate functions or requirements; (2) derive expected values by tracing the implementation; (3) cover normal paths, boundaries, invalid types/values, empty inputs, and exceptions where applicable; (4) use descriptive test names; (5) avoid network or filesystem side effects; (6) include a concise test matrix. Return ONLY valid JSON: summary, functions, test_code, cases, limitations. Each case: name, category, input, expected, rationale."""
}

def extract_json(s):
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s.strip(), flags=re.I)
    try:
        return json.loads(s)
    except Exception:
        start, end = s.find("{"), s.rfind("}")
        if start >= 0 and end > start:
            return json.loads(s[start:end+1])
        raise

def demo_generate(code, language, framework):
    """Transparent deterministic demo; not an LLM result."""
    funcs = []
    if language.lower() == "python":
        try:
            tree = ast.parse(code)
            funcs = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        except SyntaxError as e:
            return {"summary": f"Python syntax error at line {e.lineno}: {e.msg}",
                    "functions": [], "test_code": "# Fix the source syntax error before generating tests.",
                    "cases": [], "limitations": ["Demo mode uses static analysis, not an AI model."]}
    if not funcs:
        funcs = re.findall(r"(?:function\s+|def\s+|public\s+\w+\s+)([A-Za-z_$][\w$]*)\s*\(", code)
    cases = []
    for fn in funcs[:8]:
        for cat, inp, exp in [
            ("normal", "representative valid input", "behavior inferred from implementation"),
            ("boundary", "minimum/maximum or empty boundary", "boundary behavior inferred from implementation"),
            ("invalid", "invalid type/value where relevant", "error handling or rejection behavior")]:
            cases.append({"name": f"test_{fn}_{cat}", "category": cat, "input": inp,
                          "expected": exp, "rationale": f"Exercise {fn} with a {cat} scenario."})
    if not funcs:
        cases = [{"name":"manual_review_required","category":"analysis","input":"provided source",
                  "expected":"identify callable units and their contracts","rationale":"No function signature was confidently detected."}]
    if framework.lower() == "pytest" and language.lower() == "python":
        test_code = "# DEMONSTRATION TEMPLATE — review imports and expected values before execution.\n"
        for fn in funcs[:8]:
            test_code += f"\ndef test_{fn}_normal():\n    # TODO: import {fn} and replace placeholder with a verified assertion\n    assert callable({fn})\n"
        if not funcs:
            test_code += "\ndef test_placeholder():\n    assert True  # Replace with a test derived from the source code\n"
    else:
        test_code = f"// Demonstration mode: generated a test plan for {framework}.\n// Select Gemini AI mode for framework-specific executable tests.\n"
        test_code += "\n".join(f"// {c['name']}: {c['category']} — {c['input']}" for c in cases)
    return {"summary": f"Demo analysis detected {len(funcs)} function(s). This is a heuristic demonstration, not AI-generated verified tests.",
            "functions": funcs, "test_code": test_code, "cases": cases,
            "limitations": ["Demo mode is heuristic and does not understand full program semantics.",
                            "Review expected values and imports before relying on generated tests.",
                            "Use Gemini mode for LLM-based generation."]}

@app.get("/")
def home():
    return render_template("index.html", prompts=SYSTEM_PROMPTS)

@app.post("/generate")
def generate():
    data = request.get_json(force=True)
    code = (data.get("code") or "").strip()
    language = data.get("language", "Python")
    framework = data.get("framework", "pytest")
    version = data.get("version", "v3")
    mode = data.get("mode", "demo")
    if not code:
        return jsonify({"error":"Please paste source code first."}), 400
    if len(code) > 50000:
        return jsonify({"error":"Source code is too long (maximum 50,000 characters)."}), 400

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if mode == "gemini" and api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            prompt = (SYSTEM_PROMPTS.get(version, SYSTEM_PROMPTS["v3"]) +
                      f"\nLanguage: {language}\nFramework: {framework}\n\nSOURCE CODE:\n{code}")
            response = client.models.generate_content(model=model, contents=prompt)
            result = extract_json(response.text or "")
            result["mode"] = "Gemini AI"
            result["model"] = model
            return jsonify(result)
        except Exception as e:
            return jsonify({"error":f"Gemini request failed: {str(e)}. Check API key, model, and network, or use demo mode."}), 500
    if mode == "gemini" and not api_key:
        return jsonify({"error":"GEMINI_API_KEY is not configured on the server. Follow README instructions or use demo mode."}), 400
    result = demo_generate(code, language, framework)
    result["mode"] = "Demonstration (heuristic; not AI)"
    result["model"] = "Local demo engine"
    return jsonify(result)

@app.post("/validate-python")
def validate_python():
    data = request.get_json(force=True)
    source = data.get("source", "")
    tests = data.get("tests", "")
    if not source.strip() or not tests.strip():
        return jsonify({"error":"Both source code and test code are required."}), 400
    # This is a local educational prototype, not a hardened sandbox.
    # Disable obvious dangerous imports/builtins before running a short-lived subprocess.
    forbidden = ["import os", "import subprocess", "import socket", "import requests", "open(", "__import__"]
    if any(x in source + "\n" + tests for x in forbidden):
        return jsonify({"error":"Validation blocked: potentially unsafe import or operation detected."}), 400
    with tempfile.TemporaryDirectory() as td:
        src_path = os.path.join(td, "user_module.py")
        test_path = os.path.join(td, "test_user_module.py")
        # tests can import user_module
        with open(src_path, "w", encoding="utf-8") as f: f.write(source)
        with open(test_path, "w", encoding="utf-8") as f:
            f.write("import user_module\n" + tests.replace("from solution import", "from user_module import"))
        try:
            p = subprocess.run([sys.executable, "-m", "pytest", "-q", test_path],
                               cwd=td, capture_output=True, text=True, timeout=5)
            return jsonify({"returncode":p.returncode, "passed":p.returncode == 0,
                            "output":(p.stdout + "\n" + p.stderr)[-5000:]})
        except subprocess.TimeoutExpired:
            return jsonify({"error":"Test execution timed out after 5 seconds."}), 408
        except Exception as e:
            return jsonify({"error":str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
