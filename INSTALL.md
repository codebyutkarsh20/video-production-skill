# Install Video Production

Source: [codebyutkarsh20/video-production-skill](https://github.com/codebyutkarsh20/video-production-skill). The installable skill lives at `skills/video-production/`; the repository root includes examples and contributor tools.

## Standard installer

With Node.js (tested on 22.18 and 24.19), run from the project where you want the skill:

```sh
npx skills add codebyutkarsh20/video-production-skill --skill video-production
```

Choose your coding agent when prompted. The current [Skills CLI](https://github.com/vercel-labs/skills/blob/main/docs/commands.md) supports selecting agents and project/global scope:

```sh
# Project-local, explicit agents, no interactive prompts
npx skills add codebyutkarsh20/video-production-skill --skill video-production --agent codex claude-code cursor --yes

# Global installation; choose the agent(s) you actually use
npx skills add codebyutkarsh20/video-production-skill --skill video-production --global --agent codex --yes

# Discover without installing
npx skills add codebyutkarsh20/video-production-skill --list
```

The installer may use a shared `.agents/skills` location and agent-specific links. Exact discovery/reload behavior belongs to your host. Use `--copy` where symlinks are unsuitable. Installing instructions does not install FFmpeg, browser tools, models or paid accounts.

For the fixed v0.3.0 source rather than the changing default branch:

```sh
npx skills add https://github.com/codebyutkarsh20/video-production-skill/tree/v0.3.0/skills/video-production --yes
```

## Ask your agent to install it

Paste this into your coding agent:

> Install the `video-production` Agent Skill from https://github.com/codebyutkarsh20/video-production-skill/tree/main/skills/video-production into this project's skill directory for the current agent. Read its SKILL.md and required support files before use. Preserve an existing installation unless I requested an update. Check the installed helper with `doctor`, report the destination and missing dependencies, and make no paid provider calls or unrelated configuration changes.

For Codex with the built-in skill installer, you can instead ask:

> Use the skill installer to install `skills/video-production` from the GitHub repository `codebyutkarsh20/video-production-skill`.

That installer normally uses the user's Codex skills directory. If you want project scope or a custom destination, say so explicitly.

## Download without Node.js

Download [the v0.3.0 standalone skill ZIP](https://github.com/codebyutkarsh20/video-production-skill/releases/download/v0.3.0/video-production-skill-0.3.0.zip) and its [SHA-256 checksum](https://github.com/codebyutkarsh20/video-production-skill/releases/download/v0.3.0/video-production-skill-0.3.0.zip.sha256), or browse [the latest release](https://github.com/codebyutkarsh20/video-production-skill/releases/latest). Extract the `video-production` folder into the skill directory supported by your host. Preserve the complete folder: SKILL.md, LICENSE, references, scripts and optional agent metadata.

Common locations:

| Host | Project scope | User scope |
|---|---|---|
| Codex/shared Agent Skills | `.agents/skills/video-production` | `~/.codex/skills/video-production` or the host's shared discovery path |
| Claude Code | `.claude/skills/video-production` | `~/.claude/skills/video-production` |
| Cursor | `.agents/skills/video-production` with the tested Skills CLI | Use the host-supported scope or Skills CLI |

Choose one canonical installation per scope. Check existing files before copying; avoid nested `video-production/video-production` folders. Refer to your agent's current documentation if its discovery paths differ.

## Verify and use

Run the helper from the installed folder:

```sh
python3 /path/to/video-production/scripts/video_tools.py doctor
```

Planning works without a renderer. The bundled media helper needs Python 3.10+ and FFmpeg/ffprobe with the reported capabilities. Footage reading and face tracking also need [uv](https://docs.astral.sh/uv/), which fetches each script's pinned dependencies on first run; a transcription model downloads only after you approve it. Install optional dependencies only for the route you use; the host chooses its supported browser, TTS or generation tools.

Example invocation:

> Use $video-production to create a 45–60 second preview from my source material. Use English narration and captions, report actual checks, and stop for my review before the full video.

## Updates and removal

For a Skills CLI installation:

```sh
npx skills check
npx skills update video-production
npx skills remove video-production
```

Use the same project/global scope as installation. A manual installation is updated by reviewing and replacing its complete folder; do not erase a user's local customization without agreement.

The package follows the [Agent Skills specification](https://agentskills.io/specification). Format compatibility is broader than tested runtime support: see [the support matrix](README.md#support-and-limits) and [release evidence](docs/release-evidence.md).
