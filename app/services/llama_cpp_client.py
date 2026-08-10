"""
app/services/anthropic_client.py

Local text-generation via llama-cpp-python + a 4-bit quantized GGUF model —
CPU-friendly, fits comfortably in 16GB RAM. No Ollama, no GPU required.
Public interface unchanged.
"""
# import os
# import asyncio
# import logging
# import queue
# import threading
# from collections.abc import AsyncGenerator
# from functools import lru_cache

# from huggingface_hub import hf_hub_download
# from llama_cpp import Llama

# logger = logging.getLogger(__name__)

# # Qwen2.5-3B-Instruct, 4-bit quantized — ~2GB on disk, ~3-4GB RAM at runtime.
# REPO_ID = "Qwen/Qwen2.5-3B-Instruct-GGUF"
# FILENAME = "qwen2.5-3b-instruct-q4_k_m.gguf"

# # Must match the n_ctx passed to Llama() below — kept as one constant so the
# # context-fitting logic can't silently drift out of sync with the model.
# N_CTX = 4096
# MAX_OUTPUT_TOKENS = 512
# # Buffer subtracted from the budget on top of MAX_OUTPUT_TOKENS, to absorb
# # per-message chat-template overhead (role wrappers etc.) that isn't
# # captured by tokenizing raw content strings alone.
# SAFETY_MARGIN = 64


# @lru_cache
# def _load_model():
#     """Downloads (first run only, cached after) and loads the quantized model."""
#     model_path = hf_hub_download(repo_id=REPO_ID, filename=FILENAME)
#     return Llama(
#         model_path=model_path,
#         n_ctx=N_CTX,       # context window — plenty for chat + retrieved FAQ/course text
#         n_threads=max((os.cpu_count() or 2) - 1, 1),   # None = auto-detect available CPU cores
#         verbose=False,
#     )


# def _count_tokens(llm: Llama, text: str) -> int:
#     if not text:
#         return 0
#     return len(llm.tokenize(text.encode("utf-8"), add_bos=False))


# def _truncate_to_token_budget(llm: Llama, text: str, max_tokens: int) -> str:
#     """Truncate text (keeping the start, dropping the end) to at most max_tokens tokens."""
#     if max_tokens <= 0:
#         return ""
#     tokens = llm.tokenize(text.encode("utf-8"), add_bos=False)
#     if len(tokens) <= max_tokens:
#         return text
#     truncated_tokens = tokens[:max_tokens]
#     return llm.detokenize(truncated_tokens).decode("utf-8", errors="ignore")


# def _fit_messages_to_context(llm: Llama, chat_messages: list[dict]) -> list[dict]:
#     """
#     Ensures system_prompt + history + reserved output tokens fits in N_CTX.

#     Root cause this exists for: system_prompt size varies turn to turn
#     (retrieved FAQ chunks, matched courses, running summary), and history
#     grows with the conversation. Without this, on some turns the prompt
#     silently exceeded N_CTX and llama.cpp either errored mid-generation or
#     cut off unpredictably.

#     Strategy, in order:
#       1. Drop oldest non-system messages first (same "prefer recent
#          context" principle chatbot_service.py already applies via
#          KEEP_RECENT_VERBATIM), until history + system fits the budget.
#       2. If the system message ALONE still doesn't fit even with all
#          history dropped (large FAQ/course retrieval on that turn), the
#          system prompt's content is truncated to fit, with a warning
#          logged. This must degrade, not raise — the system message can't
#          be dropped without losing the assistant's grounding entirely, but
#          a hard failure here means the request produces literally nothing,
#          which is worse than an answer grounded in partial context.
#     """
#     system_msg = chat_messages[0]
#     other_msgs = list(chat_messages[1:])

#     def total_tokens(msgs: list[dict]) -> int:
#         # +4 tokens/message as a rough allowance for chat-template role
#         # wrapper overhead — not exact, but conservative enough to avoid
#         # sailing right up to the edge and overflowing anyway.
#         return sum(_count_tokens(llm, m["content"]) + 4 for m in msgs)

#     budget = N_CTX - MAX_OUTPUT_TOKENS - SAFETY_MARGIN

#     while other_msgs and total_tokens([system_msg, *other_msgs]) > budget:
#         other_msgs.pop(0)  # drop oldest first, keep most recent turns intact

#     system_tokens = total_tokens([system_msg])
#     if system_tokens > budget:
#         logger.warning(
#             "System prompt (%s tokens) exceeds context budget (%s tokens) even with all "
#             "history dropped — truncating system prompt content. If this happens often, "
#             "lower FAQ top_k / course context size, or raise N_CTX.",
#             system_tokens,
#             budget,
#         )
#         truncated_content = _truncate_to_token_budget(llm, system_msg["content"], max(budget - 4, 0))
#         system_msg = {**system_msg, "content": truncated_content}

#     return [system_msg, *other_msgs]


# async def get_chat_completion(
#     system_prompt: str,
#     messages: list[dict],
#     model: str | None = None,  # kept for interface compatibility; unused here
# ) -> str:
#     llm = _load_model()

#     chat = [{"role": "system", "content": system_prompt}, *messages]
#     chat = _fit_messages_to_context(llm, chat)

#     result = llm.create_chat_completion(messages=chat, max_tokens=MAX_OUTPUT_TOKENS, temperature=0.7)

#     return result["choices"][0]["message"]["content"]


# # Sentinel used to signal "no more chunks" across the thread/asyncio boundary.
# _STREAM_DONE = object()


# async def get_chat_completion_stream(
#     system_prompt: str,
#     messages: list[dict],
#     model: str | None = None,  # kept for interface compatibility; unused here
# ) -> AsyncGenerator[str, None]:
#     """
#     Yields response text incrementally as llama.cpp generates it.

#     llama-cpp-python's create_chat_completion(stream=True) returns a plain
#     synchronous generator — each next() call blocks the calling thread while
#     the model produces the next token(s). Iterating it directly with
#     `async for` would block the whole event loop, not just this request.

#     So generation runs on a background thread; each chunk is pushed onto a
#     thread-safe queue.Queue, and this coroutine pulls from that queue via
#     run_in_executor (which itself uses a thread, but only to wait on the
#     queue — a cheap, near-instant wait, not the expensive model call).

#     Exceptions raised inside the generation thread are relayed through the
#     queue and re-raised here, rather than silently vanishing in a
#     background thread.
#     """
#     llm = _load_model()
#     chat = [{"role": "system", "content": system_prompt}, *messages]
#     chat = _fit_messages_to_context(llm, chat)

#     chunk_queue: queue.Queue = queue.Queue()

#     def _produce() -> None:
#         try:
#             stream = llm.create_chat_completion(
#                 messages=chat, max_tokens=MAX_OUTPUT_TOKENS, temperature=0.7, stream=True
#             )
#             for piece in stream:
#                 delta = piece["choices"][0].get("delta", {})
#                 content = delta.get("content")
#                 if content:
#                     chunk_queue.put(content)
#         except Exception as exc:  # noqa: BLE001 - deliberately broad, relayed not swallowed
#             chunk_queue.put(exc)
#         finally:
#             chunk_queue.put(_STREAM_DONE)

#     # daemon=True so a lingering generation thread can't block process exit
#     # (e.g. if a client disconnects mid-stream and nothing else joins it).
#     thread = threading.Thread(target=_produce, daemon=True)
#     thread.start()

#     loop = asyncio.get_running_loop()
#     while True:
#         item = await loop.run_in_executor(None, chunk_queue.get)
#         if item is _STREAM_DONE:
#             break
#         if isinstance(item, Exception):
#             raise item
#         yield item