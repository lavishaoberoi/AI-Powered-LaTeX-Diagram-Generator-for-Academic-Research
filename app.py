"""
Flask Application — AI-Powered LaTeX Diagram Generator
IBM Watsonx.ai + Granite | Academic Research Tool
"""
import os
import uuid
import base64
import logging
from pathlib import Path

from flask import (
    Flask, request, jsonify, session,
    send_file, render_template, abort,
)
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from watsonx_client import (
    generate_diagram, refine_diagram,
    fix_latex_errors, interpret_sketch,
    suggest_optimizations,
)
from latex_service import compile_latex, validate_latex_syntax
from diagram_history import (
    add_diagram, get_history, get_diagram,
    delete_diagram, clear_history,
)

# ──────────────────────────────────────────────────────────────────────────────
# App bootstrap
# ──────────────────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

UPLOAD_FOLDER = Path(os.getenv("UPLOAD_FOLDER", "uploads"))
OUTPUT_FOLDER = Path(os.getenv("OUTPUT_FOLDER", "outputs"))
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg"}

CORS(app, supports_credentials=True)


def _get_session_id() -> str:
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def _safe_read_file(path: str | None) -> str | None:
    """Read a file as base64, return None if missing."""
    if not path:
        return None
    p = Path(path)
    if p.exists():
        return base64.b64encode(p.read_bytes()).decode("utf-8")
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Frontend
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ──────────────────────────────────────────────────────────────────────────────
# API: Generate diagram from text
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True)
    description   = (data.get("description") or "").strip()
    style_profile = data.get("style_profile")
    diagram_type  = data.get("diagram_type")
    auto_compile  = data.get("auto_compile", True)

    if not description:
        return jsonify({"error": "description is required"}), 400

    try:
        result = generate_diagram(description, style_profile=style_profile, diagram_type=diagram_type)
    except EnvironmentError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.exception("generate_diagram failed")
        return jsonify({"error": f"AI generation failed: {str(e)}"}), 500

    latex_code  = result["latex_code"]
    explanation = result["explanation"]
    dtype       = result["diagram_type"]

    # Static validation
    issues = validate_latex_syntax(latex_code)

    # Compile
    compile_result = {"success": False, "error_log": "Compilation skipped."}
    if auto_compile and latex_code:
        diagram_id = str(uuid.uuid4())
        compile_result = compile_latex(latex_code, diagram_id)

        # Auto-fix on first compile failure
        if not compile_result["success"]:
            fix_result = fix_latex_errors(latex_code, compile_result["error_log"], style_profile)
            if fix_result["latex_code"]:
                latex_code  = fix_result["latex_code"]
                explanation = fix_result["explanation"]
                diagram_id2 = str(uuid.uuid4())
                compile_result = compile_latex(latex_code, diagram_id2)
                if compile_result["success"]:
                    diagram_id = diagram_id2

    sid = _get_session_id()
    record = add_diagram(
        session_id=sid,
        latex_code=latex_code,
        explanation=explanation,
        diagram_type=dtype,
        pdf_path=compile_result.get("pdf_path"),
        png_path=compile_result.get("png_path"),
        prompt=description,
    )

    return jsonify({
        "diagram_id":   record["id"],
        "version":      record["version"],
        "latex_code":   latex_code,
        "explanation":  explanation,
        "diagram_type": dtype,
        "issues":       issues,
        "compiled":     compile_result["success"],
        "error_log":    compile_result.get("error_log"),
        "png_base64":   _safe_read_file(compile_result.get("png_path")),
    })


# ──────────────────────────────────────────────────────────────────────────────
# API: Refine existing diagram
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/refine", methods=["POST"])
def api_refine():
    data = request.get_json(force=True)
    current_code       = (data.get("current_code") or "").strip()
    refinement_request = (data.get("refinement_request") or "").strip()
    style_profile      = data.get("style_profile")
    auto_compile       = data.get("auto_compile", True)

    if not current_code or not refinement_request:
        return jsonify({"error": "current_code and refinement_request are required"}), 400

    try:
        result = refine_diagram(current_code, refinement_request, style_profile=style_profile)
    except Exception as e:
        logger.exception("refine_diagram failed")
        return jsonify({"error": str(e)}), 500

    latex_code  = result["latex_code"]
    explanation = result["explanation"]

    compile_result = {"success": False, "error_log": "Compilation skipped."}
    if auto_compile and latex_code:
        diagram_id = str(uuid.uuid4())
        compile_result = compile_latex(latex_code, diagram_id)
        if not compile_result["success"]:
            fix_result = fix_latex_errors(latex_code, compile_result["error_log"], style_profile)
            if fix_result["latex_code"]:
                latex_code  = fix_result["latex_code"]
                explanation = fix_result["explanation"]
                diagram_id2 = str(uuid.uuid4())
                compile_result = compile_latex(latex_code, diagram_id2)

    sid = _get_session_id()
    record = add_diagram(
        session_id=sid,
        latex_code=latex_code,
        explanation=explanation,
        diagram_type=data.get("diagram_type", "refined"),
        pdf_path=compile_result.get("pdf_path"),
        png_path=compile_result.get("png_path"),
        prompt=refinement_request,
    )

    return jsonify({
        "diagram_id":  record["id"],
        "version":     record["version"],
        "latex_code":  latex_code,
        "explanation": explanation,
        "compiled":    compile_result["success"],
        "error_log":   compile_result.get("error_log"),
        "png_base64":  _safe_read_file(compile_result.get("png_path")),
    })


# ──────────────────────────────────────────────────────────────────────────────
# API: Compile custom LaTeX code
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/compile", methods=["POST"])
def api_compile():
    data       = request.get_json(force=True)
    latex_code = (data.get("latex_code") or "").strip()
    if not latex_code:
        return jsonify({"error": "latex_code is required"}), 400

    issues = validate_latex_syntax(latex_code)
    diagram_id = str(uuid.uuid4())
    result = compile_latex(latex_code, diagram_id)

    return jsonify({
        "compiled":   result["success"],
        "error_log":  result.get("error_log"),
        "png_base64": _safe_read_file(result.get("png_path")),
        "pdf_url":    f"/api/download/pdf/{diagram_id}" if result["success"] else None,
        "issues":     issues,
    })


# ──────────────────────────────────────────────────────────────────────────────
# API: Upload and interpret sketch
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/sketch", methods=["POST"])
def api_sketch():
    description = request.form.get("description", "")
    style_profile = request.form.get("style_profile")
    file = request.files.get("sketch")

    if not file or not _allowed_file(file.filename):
        return jsonify({"error": "Valid image file required (png/jpg/gif/svg/webp)"}), 400

    filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
    file_path = UPLOAD_FOLDER / filename
    file.save(str(file_path))

    # Read image as base64 for potential vision model use
    img_b64 = base64.b64encode(file_path.read_bytes()).decode("utf-8")

    try:
        result = interpret_sketch(img_b64, additional_description=description, style_profile=style_profile)
    except Exception as e:
        logger.exception("interpret_sketch failed")
        return jsonify({"error": str(e)}), 500

    latex_code  = result["latex_code"]
    explanation = result["explanation"]
    dtype       = result["diagram_type"]

    diagram_id = str(uuid.uuid4())
    compile_result = compile_latex(latex_code, diagram_id)

    sid = _get_session_id()
    record = add_diagram(
        session_id=sid,
        latex_code=latex_code,
        explanation=explanation,
        diagram_type=dtype,
        pdf_path=compile_result.get("pdf_path"),
        png_path=compile_result.get("png_path"),
        prompt=f"[sketch] {description}",
    )

    return jsonify({
        "diagram_id":  record["id"],
        "version":     record["version"],
        "latex_code":  latex_code,
        "explanation": explanation,
        "diagram_type": dtype,
        "compiled":    compile_result["success"],
        "error_log":   compile_result.get("error_log"),
        "png_base64":  _safe_read_file(compile_result.get("png_path")),
    })


# ──────────────────────────────────────────────────────────────────────────────
# API: Suggest optimizations
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/optimize", methods=["POST"])
def api_optimize():
    data = request.get_json(force=True)
    latex_code    = (data.get("latex_code") or "").strip()
    style_profile = data.get("style_profile")
    if not latex_code:
        return jsonify({"error": "latex_code is required"}), 400

    try:
        result = suggest_optimizations(latex_code, style_profile=style_profile)
    except Exception as e:
        logger.exception("suggest_optimizations failed")
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "suggestions":    result["suggestions"],
        "improved_code":  result["improved_code"],
    })


# ──────────────────────────────────────────────────────────────────────────────
# API: History
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/history", methods=["GET"])
def api_history():
    sid = _get_session_id()
    history = get_history(sid)
    # Strip heavy latex_code from list view for speed
    summary = [
        {k: v for k, v in r.items() if k != "latex_code"}
        for r in history
    ]
    return jsonify({"history": summary, "total": len(summary)})


@app.route("/api/history/<diagram_id>", methods=["GET"])
def api_get_diagram(diagram_id):
    sid = _get_session_id()
    record = get_diagram(sid, diagram_id)
    if not record:
        return jsonify({"error": "Not found"}), 404
    record["png_base64"] = _safe_read_file(record.get("png_path"))
    return jsonify(record)


@app.route("/api/history/<diagram_id>", methods=["DELETE"])
def api_delete_diagram(diagram_id):
    sid = _get_session_id()
    if delete_diagram(sid, diagram_id):
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/history", methods=["DELETE"])
def api_clear_history():
    sid = _get_session_id()
    clear_history(sid)
    return jsonify({"success": True})


# ──────────────────────────────────────────────────────────────────────────────
# API: Downloads
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/download/tex/<diagram_id>")
def download_tex(diagram_id):
    sid = _get_session_id()
    record = get_diagram(sid, diagram_id)
    if not record:
        return abort(404)
    from io import BytesIO
    buf = BytesIO(record["latex_code"].encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/x-tex",
        as_attachment=True,
        download_name=f"diagram_v{record['version']}.tex",
    )


@app.route("/api/download/pdf/<diagram_id>")
def download_pdf(diagram_id):
    # diagram_id here can be either history record id or raw compile id
    sid = _get_session_id()
    record = get_diagram(sid, diagram_id)
    if record and record.get("pdf_path"):
        pdf_path = Path(record["pdf_path"])
    else:
        # Try output folder directly
        pdf_path = OUTPUT_FOLDER / diagram_id / f"{diagram_id}.pdf"

    if not pdf_path.exists():
        return abort(404)
    return send_file(
        str(pdf_path),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"diagram_{diagram_id[:8]}.pdf",
    )


@app.route("/api/download/png/<diagram_id>")
def download_png(diagram_id):
    sid = _get_session_id()
    record = get_diagram(sid, diagram_id)
    if record and record.get("png_path"):
        png_path = Path(record["png_path"])
    else:
        png_path = OUTPUT_FOLDER / diagram_id / f"{diagram_id}.png"

    if not png_path.exists():
        return abort(404)
    return send_file(
        str(png_path),
        mimetype="image/png",
        as_attachment=True,
        download_name=f"diagram_{diagram_id[:8]}.png",
    )


# ──────────────────────────────────────────────────────────────────────────────
# API: Health check
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "model":  os.getenv("GRANITE_MODEL_ID", "unset"),
        "compiler": os.getenv("LATEX_COMPILER", "tectonic"),
    })


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    logger.info(f"Starting DiagramAI on port {port} (debug={debug})")
    app.run(host="0.0.0.0", port=port, debug=debug)
