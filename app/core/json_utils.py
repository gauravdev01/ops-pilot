import json


def parse_json_response(response: str) -> object:
    """Parse direct JSON or JSON enclosed by a complete Markdown code fence."""
    try:
        return json.loads(response)
    except json.JSONDecodeError as exc:
        lines = response.strip().splitlines()
        if (
            len(lines) >= 3
            and lines[0].strip().lower() in {"```", "```json"}
            and lines[-1].strip() == "```"
        ):
            try:
                return json.loads("\n".join(lines[1:-1]))
            except json.JSONDecodeError:
                pass
        raise ValueError("Model returned invalid JSON") from exc
