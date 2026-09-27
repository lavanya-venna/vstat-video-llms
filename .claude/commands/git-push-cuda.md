---
description: Commit and push pending changes in cuda_programming_basics to the lavanya-venna GitHub repo
---

Commit and push whatever is currently pending in the `cuda-programming-basics` repo.

Repo location: `/fsxvision_new/lavanya.venna/diffusion/cuda_programming_basics`
Remote: `origin` -> `git@github-personal:lavanya-venna/cuda-programming-basics.git`
(pushes as the `lavanya-venna` personal GitHub account, via the `github-personal` SSH
host alias in `~/.ssh/config` — this is a different account/key from the user's other
GitHub work, do not push this repo through the default `github.com` host)

Steps:
1. `cd` into the repo and run `git status` to see what's changed. If there is nothing
   to commit, say so and stop.
2. Confirm `models/` stays out of the diff — it's gitignored on purpose, never add it
   even with `git add -A` overrides.
3. Review the diff/new files briefly for anything that looks like a secret, credential,
   or large binary artifact before staging (compiled binaries such as prior `.o`/ELF
   build outputs shouldn't be committed — flag them instead of adding).
4. Stage the relevant files, write a concise commit message describing what changed
   (based on the actual diff, not a generic message), and commit.
5. Push to `origin main`.
6. Report back what was committed and pushed (or that there was nothing to do).
