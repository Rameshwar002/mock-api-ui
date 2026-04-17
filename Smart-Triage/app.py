import os
import subprocess
import threading
import xml.etree.ElementTree as ET
import zipfile
import io
from flask import Flask, request, jsonify, send_from_directory, send_file

app = Flask(__name__, static_folder='public')

# Global state to track test progress and granular failures
execution_state = {
    "status": "idle",
    "total": 0,
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "test_type": "None",
    "failures": []  # List of { "name": "Test Name", "message": "Error description" }
}


def run_robot_tests(test_type, region, env):
    """Executes the Robot Framework command and parses granular results."""
    global execution_state
    execution_state = {
        "status": "running",
        "total": 0, "passed": 0, "failed": 0, "skipped": 0,
        "test_type": test_type,
        "failures": []
    }

    base_path = os.path.abspath(os.path.dirname(__file__))
    results_dir = os.path.join(base_path, "results")
    tests_dir = os.path.join(base_path, "tests")

    # Ensure results directory exists
    os.makedirs(results_dir, exist_ok=True)

    # Robot Command
    cmd = [
        "python", "-m", "robot",
        "--outputdir", results_dir,
        "--variable", f"REGION:{region}",
        "--variable", f"ENV:{env}",
        "--include", test_type.lower(),
        tests_dir
    ]

    try:
        # Execute Robot Framework
        subprocess.run(cmd, capture_output=True, text=True)

        # Parse output.xml for granular failure details
        output_xml = os.path.join(results_dir, "output.xml")
        if os.path.exists(output_xml):
            tree = ET.parse(output_xml)
            root = tree.getroot()

            # 1. Extract Overall Statistics
            for stat in root.findall(".//statistics/total/stat"):
                if stat.text == 'All Tests':
                    execution_state.update({
                        "passed": int(stat.get('pass', 0)),
                        "failed": int(stat.get('fail', 0)),
                        "skipped": int(stat.get('skip', 0)),
                        "total": int(stat.get('pass', 0)) + int(stat.get('fail', 0)) + int(stat.get('skip', 0))
                    })
                    break

            # 2. Extract Individual Failed Test Cases (Agentic Logic)
            failed_tests = []
            for test in root.findall(".//test"):
                status_tag = test.find("status")
                if status_tag is not None and status_tag.get("status") == "FAIL":
                    failed_tests.append({
                        "name": test.get("name"),
                        "message": status_tag.text if status_tag.text else "No specific error message captured."
                    })
            execution_state["failures"] = failed_tests

    except Exception as e:
        print(f"Execution Error: {e}")

    execution_state["status"] = "completed"


# --- ROUTES ---

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')


@app.route('/chat', methods=['POST'])
def handle_chat():
    """Simple NLU to extract test parameters."""
    user_text = request.json.get("message", "").lower()

    test_type = next((t for t in ["sanity", "regression", "smoke"] if t in user_text), "sanity")
    region = next((r for r in ["us", "eu", "apac"] if r in user_text), "us")
    env = next((e for e in ["dev", "prod", "int", "stage"] if e in user_text), "dev")

    return jsonify({
        "type": "confirmation",
        "message": f"I've prepared a **{test_type.upper()}** run for **{region.upper()}** on **{env.upper()}**. Proceed?",
        "params": {
            "test_type": test_type.capitalize(),
            "region": region.upper(),
            "env": env.upper()
        }
    })


@app.route('/confirm_run', methods=['POST'])
def confirm_run():
    """Starts the test execution."""
    params = request.json.get("params")
    thread = threading.Thread(
        target=run_robot_tests,
        args=(params['test_type'], params['region'], params['env'])
    )
    thread.start()
    return jsonify({"status": "started"})


@app.route('/status')
def get_status():
    """Returns current state including the failures list."""
    return jsonify(execution_state)


@app.route('/results/<path:filename>')
def serve_results(filename):
    return send_from_directory('results', filename)


@app.route('/download_results')
def download_results():
    """Zips the results folder."""
    base_path = os.path.abspath(os.path.dirname(__file__))
    results_dir = os.path.join(base_path, "results")

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(results_dir):
            for file in files:
                zf.write(os.path.join(root, file), file)

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"Execution_Report_{execution_state['test_type']}.zip"
    )


@app.route('/raise_bug', methods=['POST'])
def raise_bug():
    """Simulates Jira Defect Creation for specific tests."""
    data = request.json
    # Logic: Uses the provided title and description for specific test failures
    bug_id = "NEX-" + str(os.urandom(2).hex().upper())

    return jsonify({
        "status": "success",
        "bug_id": bug_id,
        "summary": data.get('title'),
        "description": data.get('description'),
        "attachments": ["report.html", "log.html"]
    })


if __name__ == '__main__':
    if not os.path.exists('results'):
        os.makedirs('results')
    app.run(port=8000, debug=True)