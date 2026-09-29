"""Raise vstat's hardcoded 4096-token request cap without editing vstat/.

vstat/lmms_eval/models/simple/openai.py:564 does:

    max_new_tokens = min(request_gen_kwargs.get("max_new_tokens", 1024), 4096)

which silently clamps every request to 4096 output tokens regardless of the
task's `generation_kwargs.max_new_tokens` (16384 for vstat_prompt1). That 4096
is a hardcoded literal inside a closure, so it can't be overridden via config.

This patches the openai-python SDK's Completions.create instead: it rewrites
the outgoing max_tokens/max_completion_tokens value right before the request
is sent, so the model gets the task's real token budget. Import this module
before lmms_eval's CLI runs (see run_patched.py).
"""

import os

from openai.resources.chat.completions.completions import Completions

RAISED_CAP = int(os.environ.get("VSTAT_MAX_TOKENS_CAP", "19000"))
_CLAMPED_VALUE = 4096

_original_create = Completions.create


def _patched_create(self, **kwargs):
    for key in ("max_tokens", "max_completion_tokens"):
        if kwargs.get(key) == _CLAMPED_VALUE:
            kwargs[key] = RAISED_CAP
    return _original_create(self, **kwargs)


Completions.create = _patched_create
