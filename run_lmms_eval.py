"""
Launcher that forces pyav for chat-template video decoding.

Why: this environment has no system FFmpeg shared libraries and no sudo to
install one. transformers' BaseVideoProcessor.fetch_videos() hardcodes
backend="torchcodec" first, falling back to "torchvision" only if the
torchcodec *package* is absent -- it never tries "pyav" or "decord", both of
which are installed here and bundle their own codecs (no system ffmpeg
needed). torchcodec was uninstalled from this env, but the torchvision
fallback itself is broken too (torchvision.io.read_video was removed in this
torchvision version). This monkeypatches fetch_videos to use pyav instead,
without touching the vstat repo or any installed package files.

Usage: identical to `python -m lmms_eval ...` -- just run this file instead.
"""

import sys

from transformers import video_processing_utils as _vpu
from transformers.video_utils import load_video as _load_video


def _fetch_videos_pyav(self, video_url_or_urls, sample_indices_fn=None):
    if isinstance(video_url_or_urls, list):
        return list(
            zip(*[self.fetch_videos(x, sample_indices_fn=sample_indices_fn) for x in video_url_or_urls])
        )
    return _load_video(video_url_or_urls, backend="pyav", sample_indices_fn=sample_indices_fn)


_vpu.BaseVideoProcessor.fetch_videos = _fetch_videos_pyav

from lmms_eval.__main__ import cli_evaluate  # noqa: E402

if __name__ == "__main__":
    cli_evaluate()
