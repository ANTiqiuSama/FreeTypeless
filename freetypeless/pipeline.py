"""把一段录音变成最终要输入的文字。"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np

from . import prompts
from .audio import split_for_upload, to_wav_bytes

log = logging.getLogger(__name__)


@dataclass
class Context:
    exe: str = ""
    title: str = ""
    hwnd: int = 0
    selected_text: str | None = None


@dataclass
class Result:
    mode: str
    raw: str = ""
    text: str = ""
    action: str = "paste"  # paste / show / none
    note: str = ""
    timings: dict = field(default_factory=dict)


class Processor:
    def __init__(self, cfg, client):
        self.cfg = cfg
        self.client = client

    # -------------------------------------------------------- ASR
    def transcribe(self, pcm: np.ndarray) -> str:
        chunks = split_for_upload(pcm)
        model = self.cfg.get("asr_model")
        lang = self.cfg.get("asr_language")
        if len(chunks) == 1:
            return self.client.transcribe(to_wav_bytes(chunks[0]), model, lang).strip()
        with ThreadPoolExecutor(max_workers=4) as ex:
            parts = list(ex.map(lambda c: self.client.transcribe(to_wav_bytes(c), model, lang), chunks))
        return "".join(p.strip() for p in parts)

    def _llm(self, model_key: str, messages: list, raw_len: int) -> str:
        return self.client.chat(
            self.cfg.get(model_key), messages,
            thinking=bool(self.cfg.get("llm_thinking")),
            max_tokens=max(1024, raw_len * 4),
        )

    # -------------------------------------------------------- main
    def process(self, mode: str, pcm: np.ndarray, ctx: Context) -> Result:
        import time

        res = Result(mode=mode)
        engine = self.cfg.get("engine")
        reps = self.cfg.get("replacements")
        t0 = time.monotonic()

        if mode in ("dictate", "translate") and engine == "omni":
            system = prompts.omni_system(self.cfg, ctx.exe, ctx.title, translate=(mode == "translate"))
            out = self.client.audio_chat(self.cfg.get("omni_model"), to_wav_bytes(pcm), system,
                                         "请按规则处理这段录音，只输出 <out>…</out>。",
                                         thinking=bool(self.cfg.get("llm_thinking")))
            res.timings["omni"] = time.monotonic() - t0
            _, text = prompts.extract_out(out)
            res.raw = text
            res.text = prompts.apply_replacements(text, reps)
            if not res.text:
                res.action = "none"
            return res

        raw = self.transcribe(pcm)
        res.timings["asr"] = time.monotonic() - t0
        res.raw = raw
        if prompts.is_effectively_empty(raw):
            res.action = "none"
            res.note = "未识别到语音"
            return res

        if mode == "command":
            return self._command(res, raw, ctx)

        if engine == "asr_only" and mode == "dictate":
            res.text = prompts.apply_replacements(raw, reps)
            return res

        t1 = time.monotonic()
        try:
            out = self._llm("llm_model", prompts.dictate_messages(self.cfg, raw, ctx.exe, ctx.title,
                                                                  translate=(mode == "translate")), len(raw))
            kind, text = prompts.extract_out(out)
        except Exception as e:  # 润色失败绝不丢字：退回原始识别
            log.warning("润色失败，使用原始识别结果: %s", e)
            res.text = prompts.apply_replacements(raw, reps)
            res.note = f"润色失败，已输入原始识别：{e}"
            return res
        res.timings["llm"] = time.monotonic() - t1

        # 安全阀：防止模型“回答”了口述内容而不是整理它
        if mode == "dictate":
            if (not text and len(raw) > 8) or len(text) > len(raw) * 3 + 80:
                log.info("润色结果异常(len %d -> %d)，退回原文", len(raw), len(text))
                text = raw
        res.text = prompts.apply_replacements(text, reps)
        if not res.text:
            res.action = "none"
        return res

    def _command(self, res: Result, instruction: str, ctx: Context) -> Result:
        import time

        t1 = time.monotonic()
        if ctx.selected_text:
            out = self._llm("command_model",
                            prompts.command_messages(self.cfg, ctx.selected_text, instruction, ctx.exe, ctx.title),
                            len(ctx.selected_text) + len(instruction))
            kind, text = prompts.extract_out(out)
            res.text = text
            res.action = "show" if kind == "answer" else "paste"
        else:
            out = self._llm("command_model", prompts.ask_messages(self.cfg, instruction), 400)
            res.text = out.strip()
            res.action = "show"
        res.timings["llm"] = time.monotonic() - t1
        if not res.text:
            res.action = "none"
        return res
