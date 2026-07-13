"""
LaTeX Compilation Service
Supports: tectonic, pdflatex (local), and microservice backends.
"""
import os
import re
import shutil
import subprocess
import tempfile
import logging
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

COMPILER = os.getenv("LATEX_COMPILER", "tectonic")
LATEX_SERVICE_URL = os.getenv("LATEX_SERVICE_URL", "")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "outputs")


def _ensure_output_dir(diagram_id: str) -> Path:
    out = Path(OUTPUT_FOLDER) / diagram_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def _extract_tikz_error(log: str) -> str:
    """Pull the most relevant error lines from a pdflatex log."""
    lines = log.splitlines()
    errors = [l for l in lines if l.startswith("!") or "Error" in l or "error" in l]
    return "\n".join(errors[:15]) if errors else log[-800:]


def compile_latex(latex_code: str, diagram_id: str) -> dict:
    """
    Compile latex_code and return:
      {
        "success": bool,
        "pdf_path": str | None,
        "png_path": str | None,
        "svg_path": str | None,
        "error_log": str | None,
      }
    """
    out_dir = _ensure_output_dir(diagram_id)

    if COMPILER == "microservice" and LATEX_SERVICE_URL:
        return _compile_via_microservice(latex_code, diagram_id, out_dir)
    elif COMPILER == "tectonic":
        return _compile_tectonic(latex_code, diagram_id, out_dir)
    else:
        return _compile_pdflatex(latex_code, diagram_id, out_dir)


# ──────────────────────────────────────────────────────────────────────────────
# Tectonic backend
# ──────────────────────────────────────────────────────────────────────────────
def _compile_tectonic(latex_code: str, diagram_id: str, out_dir: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_file = Path(tmpdir) / f"{diagram_id}.tex"
        tex_file.write_text(latex_code, encoding="utf-8")

        try:
            result = subprocess.run(
                ["tectonic", "-X", "compile", "--outdir", str(out_dir), str(tex_file)],
                capture_output=True, text=True, timeout=60,
            )
        except FileNotFoundError:
            return {"success": False, "error_log": "tectonic not found in PATH. Install via: cargo install tectonic"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error_log": "Compilation timed out after 60 seconds."}

        pdf_path = out_dir / f"{diagram_id}.pdf"
        if result.returncode == 0 and pdf_path.exists():
            png_path = _pdf_to_png(pdf_path, out_dir, diagram_id)
            return {
                "success": True,
                "pdf_path": str(pdf_path),
                "png_path": png_path,
                "svg_path": None,
                "error_log": None,
            }
        else:
            error = result.stderr or result.stdout
            return {"success": False, "error_log": _extract_tikz_error(error)}


# ──────────────────────────────────────────────────────────────────────────────
# pdflatex backend
# ──────────────────────────────────────────────────────────────────────────────
def _compile_pdflatex(latex_code: str, diagram_id: str, out_dir: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_file = Path(tmpdir) / f"{diagram_id}.tex"
        tex_file.write_text(latex_code, encoding="utf-8")

        try:
            result = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    f"-output-directory={tmpdir}",
                    str(tex_file),
                ],
                capture_output=True, text=True, timeout=90, cwd=tmpdir,
            )
        except FileNotFoundError:
            return {"success": False, "error_log": "pdflatex not found. Install TeX Live or MiKTeX."}
        except subprocess.TimeoutExpired:
            return {"success": False, "error_log": "pdflatex timed out after 90 seconds."}

        pdf_src = Path(tmpdir) / f"{diagram_id}.pdf"
        if result.returncode == 0 and pdf_src.exists():
            pdf_path = out_dir / f"{diagram_id}.pdf"
            shutil.copy(pdf_src, pdf_path)
            png_path = _pdf_to_png(pdf_path, out_dir, diagram_id)
            return {
                "success": True,
                "pdf_path": str(pdf_path),
                "png_path": png_path,
                "svg_path": None,
                "error_log": None,
            }
        else:
            log_file = Path(tmpdir) / f"{diagram_id}.log"
            log_text = log_file.read_text(encoding="utf-8", errors="replace") if log_file.exists() else result.stderr
            return {"success": False, "error_log": _extract_tikz_error(log_text)}


# ──────────────────────────────────────────────────────────────────────────────
# Microservice backend  (e.g. LaTeX-on-HTTP / texlive-http)
# ──────────────────────────────────────────────────────────────────────────────
def _compile_via_microservice(latex_code: str, diagram_id: str, out_dir: Path) -> dict:
    try:
        resp = requests.post(
            LATEX_SERVICE_URL,
            json={"latex": latex_code},
            timeout=60,
        )
        if resp.status_code == 200:
            pdf_path = out_dir / f"{diagram_id}.pdf"
            pdf_path.write_bytes(resp.content)
            png_path = _pdf_to_png(pdf_path, out_dir, diagram_id)
            return {
                "success": True,
                "pdf_path": str(pdf_path),
                "png_path": png_path,
                "svg_path": None,
                "error_log": None,
            }
        else:
            return {"success": False, "error_log": resp.text[:800]}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error_log": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# PDF → PNG conversion (requires pdf2image + poppler)
# ──────────────────────────────────────────────────────────────────────────────
def _pdf_to_png(pdf_path: Path, out_dir: Path, diagram_id: str) -> str | None:
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(str(pdf_path), dpi=150, first_page=1, last_page=1)
        if images:
            png_path = out_dir / f"{diagram_id}.png"
            images[0].save(str(png_path), "PNG")
            return str(png_path)
    except Exception as e:
        logger.warning(f"PDF→PNG conversion failed: {e}")
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Syntax validator (static, pre-compile)
# ──────────────────────────────────────────────────────────────────────────────
def validate_latex_syntax(code: str) -> list[str]:
    """Return a list of potential issues found by static analysis."""
    issues = []
    if "\\begin{document}" not in code:
        issues.append("Missing \\begin{document}")
    if "\\end{document}" not in code:
        issues.append("Missing \\end{document}")
    if "\\begin{tikzpicture}" not in code:
        issues.append("Missing \\begin{tikzpicture}")
    if "\\end{tikzpicture}" not in code:
        issues.append("Missing \\end{tikzpicture}")
    # Check for unclosed environments
    begins = re.findall(r"\\begin\{(\w+)\}", code)
    ends   = re.findall(r"\\end\{(\w+)\}", code)
    for env in set(begins):
        if begins.count(env) != ends.count(env):
            issues.append(f"Unbalanced environment: {env}")
    return issues
