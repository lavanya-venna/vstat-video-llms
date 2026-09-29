"""Entry point for running lmms_eval with the max-tokens patch applied.

Equivalent to `python -m lmms_eval <same CLI args>`, except patch_max_tokens
is imported first so the 4096-token cap in vstat/lmms_eval/models/simple/
openai.py is raised before any request is sent. sys.argv is left untouched
(argv[0] is this script's path, which dispatch.main() never inspects), so all
existing --model/--tasks/... flags work unchanged.
"""

import patch_max_tokens  # noqa: F401  (import order matters: patches before dispatch.main())
from lmms_eval.cli.dispatch import main

if __name__ == "__main__":
    main()
