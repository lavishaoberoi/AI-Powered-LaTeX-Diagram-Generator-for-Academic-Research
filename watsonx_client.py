"""
Watsonx.ai / IBM Granite integration layer.
All AI calls are routed through this module.
"""
import os
import re
import logging
from dotenv import load_dotenv
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
from agent_instructions import (
    build_system_prompt,
    REFINEMENT_HINTS,
    ERROR_CORRECTION_PROMPT,
    SUPPORTED_DIAGRAM_TYPES,
)

load_dotenv()
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Model configuration
# ──────────────────────────────────────────────────────────────────────────────
IBM_CLOUD_API_KEY   = os.getenv("IBM_CLOUD_API_KEY")
IBM_CLOUD_URL       = os.getenv("IBM_CLOUD_URL", "https://us-south.ml.cloud.ibm.com")
WATSONX_PROJECT_ID  = os.getenv("WATSONX_PROJECT_ID")
GRANITE_MODEL_ID    = os.getenv("GRANITE_MODEL_ID", "ibm/granite-13b-instruct-v2")

_model_instance: ModelInference | None = None


def _get_model() -> ModelInference:
    global _model_instance
    if _model_instance is None:
        if not IBM_CLOUD_API_KEY:
            raise EnvironmentError("IBM_CLOUD_API_KEY not set in environment.")
        if not WATSONX_PROJECT_ID:
            raise EnvironmentError("WATSONX_PROJECT_ID not set in environment.")
        creds = Credentials(url=IBM_CLOUD_URL, api_key=IBM_CLOUD_API_KEY)
        _model_instance = ModelInference(
            model_id=GRANITE_MODEL_ID,
            credentials=creds,
            project_id=WATSONX_PROJECT_ID,
            params={
                GenParams.MAX_NEW_TOKENS: 2048,
                GenParams.MIN_NEW_TOKENS: 50,
                GenParams.TEMPERATURE:    0.2,
                GenParams.TOP_P:          0.9,
                GenParams.REPETITION_PENALTY: 1.1,
                GenParams.STOP_SEQUENCES: ["```\n\n", "Human:", "User:"],
            },
        )
        logger.info(f"Granite model initialized: {GRANITE_MODEL_ID}")
    return _model_instance


# ──────────────────────────────────────────────────────────────────────────────
# Core generation function
# ──────────────────────────────────────────────────────────────────────────────
def _call_granite(system_prompt: str, user_message: str) -> str:
    """Low-level call to the Granite model. Returns raw response text."""
    model = _get_model()
    full_prompt = f"{system_prompt}\n\nUser: {user_message}\n\nAssistant:"
    try:
        response = model.generate_text(prompt=full_prompt)
        return response if isinstance(response, str) else response.get("results", [{}])[0].get("generated_text", "")
    except Exception as e:
        logger.error(f"Granite API call failed: {e}")
        raise


def _extract_code_and_explanation(raw: str) -> tuple[str, str]:
    """
    Parse model output to separate LaTeX code block from explanation.
    Returns (latex_code, explanation).
    """
    # Try ```latex ... ``` block
    latex_match = re.search(r"```(?:latex|tex)\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if latex_match:
        code = latex_match.group(1).strip()
    else:
        # Fallback: look for \documentclass as start marker
        doc_match = re.search(r"(\\documentclass.*?\\end\{document\})", raw, re.DOTALL)
        code = doc_match.group(1).strip() if doc_match else ""

    # Explanation = everything after the code block
    explanation_raw = raw[latex_match.end():].strip() if latex_match else ""
    # Clean up explanation bullet markers
    explanation = explanation_raw if explanation_raw else "No explanation provided."
    return code, explanation


def _detect_diagram_type(description: str) -> str:
    """Heuristically detect diagram type from user description."""
    desc_lower = description.lower()
    type_keywords = {
        "neural_network":  ["neural", "network", "perceptron", "deep learning", "layer", "neuron"],
        "flowchart":       ["flow", "flowchart", "process", "decision", "algorithm", "step"],
        "circuit_diagram": ["circuit", "resistor", "capacitor", "transistor", "gate", "logic"],
        "venn_diagram":    ["venn", "intersection", "union", "overlap", "set"],
        "block_diagram":   ["block", "system", "module", "component", "architecture"],
        "state_machine":   ["state", "automaton", "transition", "finite"],
        "sequence_diagram":["sequence", "message", "actor", "interaction", "uml"],
        "bar_chart":       ["bar chart", "bar graph", "histogram"],
        "line_graph":      ["line graph", "trend", "plot", "curve"],
        "gantt_chart":     ["gantt", "schedule", "timeline", "milestone"],
        "tree_diagram":    ["tree", "hierarchy", "parent", "child", "root", "leaf"],
        "mind_map":        ["mind map", "brainstorm", "central idea"],
    }
    for dtype, keywords in type_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            return dtype
    return "block_diagram"


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────
def generate_diagram(
    description: str,
    style_profile: str = None,
    diagram_type: str = None,
) -> dict:
    """
    Generate LaTeX/TikZ code from a natural language description.
    Returns: {latex_code, explanation, diagram_type}
    """
    dtype = diagram_type or _detect_diagram_type(description)
    system = build_system_prompt(diagram_type=dtype, style_key=style_profile)
    user_msg = (
        f"Generate a complete, compilable TikZ diagram for the following request:\n\n"
        f"{description}\n\n"
        f"Diagram type: {dtype}"
    )
    raw = _call_granite(system, user_msg)
    code, explanation = _extract_code_and_explanation(raw)
    return {"latex_code": code, "explanation": explanation, "diagram_type": dtype}


def refine_diagram(
    current_code: str,
    refinement_request: str,
    style_profile: str = None,
) -> dict:
    """
    Refine an existing TikZ diagram based on a plain-English instruction.
    Returns: {latex_code, explanation}
    """
    # Enrich request with known hints
    hint_text = ""
    for key, hint in REFINEMENT_HINTS.items():
        if key in refinement_request.lower():
            hint_text += f"\nHint for '{key}': {hint}"

    system = build_system_prompt(style_key=style_profile)
    user_msg = (
        f"Here is the current TikZ diagram code:\n\n```latex\n{current_code}\n```\n\n"
        f"Apply this refinement: {refinement_request}\n"
        f"{hint_text}\n\n"
        f"Return the complete modified LaTeX document with the changes applied."
    )
    raw = _call_granite(system, user_msg)
    code, explanation = _extract_code_and_explanation(raw)
    return {"latex_code": code, "explanation": explanation}


def fix_latex_errors(
    current_code: str,
    error_log: str,
    style_profile: str = None,
) -> dict:
    """
    Ask the model to fix compilation errors in latex code.
    Returns: {latex_code, explanation}
    """
    system = build_system_prompt(style_key=style_profile)
    user_msg = ERROR_CORRECTION_PROMPT.format(error_log=error_log) + f"\n\nCurrent code:\n```latex\n{current_code}\n```"
    raw = _call_granite(system, user_msg)
    code, explanation = _extract_code_and_explanation(raw)
    return {"latex_code": code, "explanation": explanation}


def interpret_sketch(
    base64_image: str,
    additional_description: str = "",
    style_profile: str = None,
) -> dict:
    """
    Interpret a hand-drawn sketch and generate TikZ code.
    NOTE: Granite vision models may vary; this uses a text-based fallback
    where the image is described via the OCR/vision pipeline first.
    Returns: {latex_code, explanation, diagram_type}
    """
    system = build_system_prompt(style_key=style_profile)
    sketch_msg = (
        f"A researcher has uploaded a hand-drawn sketch of a diagram. "
        f"Based on the sketch description below, generate clean TikZ code:\n\n"
        f"Sketch description / OCR: {additional_description or 'Hand-drawn sketch provided.'}\n\n"
        f"Reproduce the structure faithfully, applying proper TikZ styling."
    )
    raw = _call_granite(system, sketch_msg)
    code, explanation = _extract_code_and_explanation(raw)
    dtype = _detect_diagram_type(additional_description)
    return {"latex_code": code, "explanation": explanation, "diagram_type": dtype}


def suggest_optimizations(current_code: str, style_profile: str = None) -> dict:
    """
    Suggest readability and aesthetics optimizations for a diagram.
    Returns: {suggestions: list[str], improved_code: str}
    """
    system = build_system_prompt(style_key=style_profile)
    user_msg = (
        f"Analyze this TikZ diagram code for readability, spacing, and publication quality:\n\n"
        f"```latex\n{current_code}\n```\n\n"
        f"1. List up to 5 specific improvement suggestions.\n"
        f"2. Then provide an improved version of the complete code."
    )
    raw = _call_granite(system, user_msg)
    code, explanation = _extract_code_and_explanation(raw)
    # Extract bullet suggestions from explanation
    suggestions = [l.strip("•- ").strip() for l in explanation.splitlines() if l.strip().startswith(("•", "-", "*"))]
    return {"suggestions": suggestions or [explanation], "improved_code": code}
