import re
from pathlib import Path

from lmms_eval.tasks.vstat.utils import (
    _extract_mcq_letter,
    _extract_last_integer,
    _numeric_mra,
)

# Load the prompt template at module level
_prompt_template_path = (
    Path(__file__).resolve().parents[3] / "prompts" / "evaluation_prompt_1.md"
)
with open(_prompt_template_path, "r", encoding="utf-8") as f:
    _prompt_template = f.read()


def doc_to_text_prompt1(doc, lmms_eval_specific_kwargs=None):
    """Format a doc using the structured PLAN/RECORD/READ/ANSWER prompt template.

    Fills {question} and {answer_rule} placeholders using str.replace() to avoid
    conflicts with literal curly braces in the template's examples section.
    """
    # Determine answer_rule based on doc type
    if doc["is_mcq"]:
        answer_rule = "the letter"
    elif doc.get("target_value") is not None:
        answer_rule = "the integer"
    else:
        # Open-ended text answer
        answer_rule = "the exact answer text"

    # Fill placeholders using replace (not format) to avoid curly-brace issues
    prompt = _prompt_template.replace("{question}", doc["question"])
    prompt = prompt.replace("{answer_rule}", answer_rule)

    return prompt


def _extract_answer_line(text):
    """Extract the value after 'ANSWER:' from the response text.

    Returns the last ANSWER line's value, or None if no ANSWER line found.
    """
    # Regex for ANSWER: line (multiline mode, capture everything after ANSWER:)
    pattern = r"^\s*ANSWER:\s*(.+)$"
    matches = re.findall(pattern, str(text), re.MULTILINE)

    if matches:
        # Return the last match's content, stripped
        return matches[-1].strip()
    return None


def process_results_prompt1(doc, results):
    """Score the model's response using ANSWER line extraction.

    Extracts the value after the final ANSWER: line, then applies the same
    extraction/comparison logic as the baseline, but only on that extracted value
    (not the whole response). Falls back to whole-response extraction if no
    ANSWER line is found.
    """
    # Extract raw response
    prediction = str(results[0]).strip() if results else ""

    # Try to extract the ANSWER line
    answer_line_content = _extract_answer_line(prediction)

    # Determine if numeric or MCQ
    is_numeric = (not doc["is_mcq"]) and doc.get("target_value") is not None

    # If we found an ANSWER line, parse just that content
    if answer_line_content is not None:
        if doc["is_mcq"]:
            parsed_prediction = _extract_mcq_letter(answer_line_content)
        elif is_numeric:
            parsed_prediction = _extract_last_integer(answer_line_content)
        else:
            # Open-ended text: exact match after normalization
            parsed_prediction = answer_line_content.lower()
    else:
        # Fallback: parse the entire response (old behavior)
        if doc["is_mcq"]:
            parsed_prediction = _extract_mcq_letter(prediction)
        elif is_numeric:
            parsed_prediction = _extract_last_integer(prediction)
        else:
            # Open-ended text
            parsed_prediction = prediction.lower()

    # Score
    if parsed_prediction is None:
        is_correct = False
    elif doc["is_mcq"]:
        is_correct = parsed_prediction == doc["answer_text"]
    elif is_numeric:
        is_correct = parsed_prediction == doc["target_value"]
    else:
        # Open-ended text: compare normalized versions
        is_correct = parsed_prediction == str(doc["answer_text"]).strip().lower()

    # Return metrics in the same format as baseline
    if is_numeric:
        score = _numeric_mra(parsed_prediction, doc["target_value"])
        return {"Numeric_MRA": score, "ALL_Score_avg": score}
    else:
        score = float(is_correct)
        return {"MCQ_ACC": score, "ALL_Score_avg": score}
