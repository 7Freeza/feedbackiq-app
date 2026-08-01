"""Traducción neuronal local ES→EN con CTranslate2 + OPUS-MT (sin red).

Camino principal de optimización de tokens. El diccionario solo es fallback.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from pathlib import Path

import sentencepiece as spm

from app.core.optimizer import optimize_text as dict_optimize

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_DIR = (
    Path(__file__).resolve().parent.parent.parent / "models" / "opus-mt-es-en-ct2"
)

_lock = threading.Lock()
_translator = None
_sp_src: spm.SentencePieceProcessor | None = None
_sp_tgt: spm.SentencePieceProcessor | None = None
_load_error: str | None = None
_engine_name = "none"

# Cache LRU de traducciones (textos repetidos entre lotes)
_CACHE_MAX = 4096
_cache: OrderedDict[str, str] = OrderedDict()
_cache_lock = threading.Lock()


def model_dir() -> Path:
    import os

    env = os.environ.get("FEEDBACKIQ_CT2_MODEL")
    if env:
        return Path(env)
    return _DEFAULT_MODEL_DIR


def is_ready() -> bool:
    return _translator is not None and _sp_src is not None


def engine_info() -> dict:
    return {
        "ready": is_ready(),
        "engine": _engine_name,
        "model_dir": str(model_dir()),
        "load_error": _load_error,
        "method_primary": "ctranslate2_opus_mt_es_en",
        "method_fallback": "dictionary",
        "cache_size": len(_cache),
    }


def warm_up() -> bool:
    """Carga el modelo en memoria (llamar al arrancar el servidor)."""
    global _translator, _sp_src, _sp_tgt, _load_error, _engine_name
    if is_ready():
        return True
    with _lock:
        if is_ready():
            return True
        path = model_dir()
        if not path.exists() or not (path / "model.bin").exists():
            _load_error = f"Modelo CT2 no encontrado en {path}"
            _engine_name = "dictionary_fallback"
            logger.warning(_load_error)
            return False
        try:
            import ctranslate2
            import os

            # Menos contención en laptops: 1 proceso, varios threads intra-op
            n_cpu = os.cpu_count() or 4
            intra = max(2, min(4, n_cpu // 2))
            compute = "int8"
            try:
                _translator = ctranslate2.Translator(
                    str(path),
                    device="cpu",
                    compute_type=compute,
                    inter_threads=1,
                    intra_threads=intra,
                )
            except Exception:
                _translator = ctranslate2.Translator(
                    str(path),
                    device="cpu",
                    compute_type="default",
                    inter_threads=1,
                    intra_threads=intra,
                )
                compute = "default"

            _sp_src = spm.SentencePieceProcessor()
            _sp_src.Load(str(path / "source.spm"))
            _sp_tgt = spm.SentencePieceProcessor()
            tgt = path / "target.spm"
            if tgt.exists():
                _sp_tgt.Load(str(tgt))
            else:
                _sp_tgt = _sp_src

            _engine_name = f"ctranslate2_opus_mt_es_en_{compute}"
            _load_error = None
            logger.info("Translator ready: %s", _engine_name)
            return True
        except Exception as exc:
            _translator = None
            _sp_src = None
            _sp_tgt = None
            _load_error = str(exc)
            _engine_name = "dictionary_fallback"
            logger.exception("Failed to load CT2 translator: %s", exc)
            return False


def _detokenize(tokens: list[str]) -> str:
    if _sp_tgt is not None:
        try:
            return _sp_tgt.DecodePieces(tokens).strip()
        except Exception:
            pass
    return "".join(tokens).replace("▁", " ").strip()


def _encode(text: str) -> list[str]:
    """SPM encode + </s>. Sin EOS el modelo Marian no detiene y repite."""
    assert _sp_src is not None
    pieces = _sp_src.EncodeAsPieces(text.strip())
    if not pieces or pieces[-1] != "</s>":
        pieces = pieces + ["</s>"]
    return pieces


def _cache_get(key: str) -> str | None:
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    return None


def _cache_put(key: str, value: str) -> None:
    with _cache_lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)


def translate_batch(
    texts: list[str],
    *,
    max_batch_size: int = 64,
    beam_size: int = 1,
    allow_fallback: bool = True,
) -> tuple[list[str], str]:
    """Traduce una lista de textos ES→EN.

    Returns:
        (translated_texts, method_used)
        method_used: 'ctranslate2' | 'dictionary' | 'passthrough'
    """
    if not texts:
        return [], "passthrough"

    if not is_ready():
        warm_up()

    if not is_ready():
        if allow_fallback:
            return [dict_optimize(t) for t in texts], "dictionary"
        return list(texts), "passthrough"

    assert _translator is not None
    out: list[str | None] = [None] * len(texts)
    to_run: list[tuple[int, str]] = []

    for i, t in enumerate(texts):
        if not t or not t.strip():
            out[i] = t or ""
            continue
        key = t.strip()
        hit = _cache_get(key)
        if hit is not None:
            out[i] = hit
        else:
            to_run.append((i, key))

    if not to_run:
        return [x if x is not None else "" for x in out], "ctranslate2"

    try:
        tokenized = [_encode(t) for _, t in to_run]
        max_src = max(len(t) for t in tokenized)
        # Tope corto: reseñas típicas no necesitan 256 tokens de salida
        max_dec = max(24, min(128, int(max_src * 1.5) + 6))
        results = _translator.translate_batch(
            tokenized,
            batch_type="examples",
            max_batch_size=max_batch_size,
            beam_size=beam_size,
            num_hypotheses=1,
            return_scores=False,
            max_decoding_length=max_dec,
            no_repeat_ngram_size=3,
        )
        for j, (idx, src) in enumerate(to_run):
            hyp = results[j].hypotheses[0] if results[j].hypotheses else []
            hyp = [p for p in hyp if p != "</s>"]
            translated = _detokenize(hyp) if hyp else src
            # Defensa: si la salida es vacía o casi idéntica basura, no inflar
            if not translated.strip():
                translated = src
            out[idx] = translated
            _cache_put(src, translated)
        return [x if x is not None else "" for x in out], "ctranslate2"
    except Exception as exc:
        logger.warning("CT2 batch failed, fallback dict: %s", exc)
        if allow_fallback:
            for idx, src in to_run:
                d = dict_optimize(src)
                out[idx] = d
            return [x if x is not None else "" for x in out], "dictionary"
        for idx, src in to_run:
            out[idx] = src
        return [x if x is not None else "" for x in out], "passthrough"


def translate_one(text: str) -> tuple[str, str]:
    outs, method = translate_batch([text])
    return outs[0] if outs else text, method


def dictionary_batch(texts: list[str]) -> list[str]:
    """Solo diccionario — referencia histórica (escenario a)."""
    return [dict_optimize(t) for t in texts]
