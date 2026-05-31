import requests

from config import load_config
from prompts import OPS_SYSTEM_PROMPT


class OllamaError(RuntimeError):
    pass


def _get_running_model(cfg) -> dict | None:
    response = requests.get(f"{cfg.ollama_url}/api/ps", timeout=5)
    response.raise_for_status()
    models = response.json().get("models", [])
    for model in models:
        names = {model.get("name"), model.get("model")}
        if cfg.ollama_model in names:
            return model
    return None


def _require_gpu_model(cfg, *, after_generation: bool) -> None:
    if not cfg.ollama_require_gpu:
        return

    model = _get_running_model(cfg)
    if model is None:
        if after_generation:
            raise OllamaError(
                "Ollama GPU verification failed: model was not listed in /api/ps after generation"
            )
        return

    try:
        size_vram = int(model.get("size_vram") or 0)
    except (TypeError, ValueError) as exc:
        raise OllamaError("Ollama GPU verification failed: invalid size_vram in /api/ps") from exc

    if size_vram <= 0:
        raise OllamaError(
            "Ollama model is loaded without GPU VRAM; refusing to continue. "
            "Check `ollama ps` and `nvidia-smi`, then restart/configure Ollama CUDA."
        )


def check_ollama() -> tuple[bool, str]:
    cfg = load_config()
    try:
        response = requests.get(f"{cfg.ollama_url}/api/tags", timeout=5)
        response.raise_for_status()
        models = response.json().get("models", [])
        model_names = {item.get("name") for item in models}
        if cfg.ollama_model in model_names:
            return True, f"Ollama online, model available: {cfg.ollama_model}"
        return True, f"Ollama online, model not listed: {cfg.ollama_model}"
    except requests.RequestException as exc:
        return False, f"Ollama offline or unreachable: {exc}"
    except ValueError as exc:
        return False, f"Ollama returned invalid JSON: {exc}"


def analyze_with_ollama(prompt: str, system_prompt: str = OPS_SYSTEM_PROMPT) -> str:
    cfg = load_config()
    full_prompt = f"{system_prompt}\n\n{prompt}".strip()
    payload = {
        "model": cfg.ollama_model,
        "prompt": full_prompt,
        "stream": False,
    }

    try:
        _require_gpu_model(cfg, after_generation=False)
        response = requests.post(f"{cfg.ollama_url}/api/generate", json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        _require_gpu_model(cfg, after_generation=True)
    except requests.RequestException as exc:
        raise OllamaError(f"Ollama request failed: {exc}") from exc
    except ValueError as exc:
        raise OllamaError(f"Ollama returned invalid JSON: {exc}") from exc

    answer = str(data.get("response", "")).strip()
    if not answer:
        raise OllamaError("Ollama returned an empty response")
    return answer
