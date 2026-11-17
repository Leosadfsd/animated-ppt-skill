---
name: script-to-animated-ppt
description: Turn a speech manuscript into a visually designed PPTX with native click-controlled entrance animations. Use for requests to make an animated presentation from a script, including Chinese requests such as 根据讲稿做动画PPT. Preserve the supplied story and visual direction.
---

# Script to animated PPT

Deliver an editable, genuinely animated PPTX from the user's manuscript. Use the available presentation-authoring capability for layout and rendering. The bundled Python helper adds native entrance timing without needing a commercial library or the author's local files.

## From manuscript to slides

Read the full manuscript and supplied references. Preserve its language, claims, narrative order, requested page count and ending. Clarify missing constraints only when they change the result. Otherwise state reasonable assumptions about page count, 16:9 format and click control and proceed. Do not invent supporting facts or rewrite the argument to fit a template.

Build a concise storyboard: slide purpose, exact manuscript passage, visible keywords, complete visual units and click cues. Keep the full narration in speaker notes, with external image/fact sources. Slides are prompts for the speaker, not copies of the script. Choose visual density and imagery to suit the actual subject; collage is an option, not a default requirement.

For a new text/image deck, prefer the bundled scene workflow in [scene-format.md](references/scene-format.md): detect the current environment, write a portable scene JSON, then build the editable deck, native groups, animation plan and offline click gallery in one command. Each unit's `cue` connects its screen state to the manuscript. This reduces repeated handwritten authoring code. Use the presentation-authoring tool directly for unsupported charts/tables or user templates; do not simplify required content to fit the scene schema.

Read [authoring.md](references/authoring.md) before generating the deck. Use an installed presentation skill if available, following its rendering and authoring requirements. On a Codex host without it, use a supported local authoring library and discover dependencies rather than copying machine-specific paths. Report a missing authoring capability honestly; never return a renamed static deck as animated.

## Animation plan and execution

Create complete semantic units: an intact person, photograph, logo, phrase, or native group containing paper and text. Prefer editable text. Inspect isolated assets for scraps and broken edges. Do not slice a finished slide into arbitrary rectangles: moving them exposes hidden fragments.

Give each animated top-level shape/group a unique stable name. Group related elements during authoring. One click advances one speaking cue; elements within that cue enter with staggered delays. `beat: 0` enters automatically; positive contiguous beats require clicks. Unlisted objects stay visible. `from` names the screen edge the object enters from.

Export a static draft, then run the helper using its actual installed skill directory (the paths below are relative to this SKILL.md, not the user's project directory):

```sh
python scripts/animate.py inspect draft.pptx
python scripts/animate.py apply draft.pptx motion.json animated.pptx
python scripts/animate.py inspect animated.pptx
```

Resolve exported names from `inspect`; never guess IDs from creation order. The helper refuses missing/ambiguous names, nested targets, duplicate targets and overwriting an existing output. Existing timing on a changed slide requires explicit `--replace-timing`; use only when replacement is intended. Keep the original deck.

Read [motion-format.md](references/motion-format.md) for the schema and limits. Only animate entrances with this helper. Preserve unrelated slides and native animation when editing a deck. For a picture-edge fix, replace the media locally and recheck shared-image relationships instead of round-tripping the whole animated deck through another exporter.

## Verify and hand off

First test a representative multi-click slide before scaling a complex deck. This is a production checkpoint, not a mandatory extra permission request. Render and inspect final layouts and every isolated moving asset. Check initial visibility, click order and complete units before, during and after motion. Observe the ending after its last animation settles. Distinguish ordinary clipping at the screen edge mid-flight from damaged source assets.

For scene builds, use the generated `index.html` and `click-guide.md` to inspect cumulative screen states and speaking cues before UI testing. They are static previews, not evidence of motion or timing. The generated `environment.json` can contain local paths; do not publish it with a shared example.

Open the saved output in the target WPS/PowerPoint when an authorized UI tool is available. Reopen the same file and retest a complex slide. XML timing and PNG renders are structural/static evidence only. If playback cannot be inspected, deliver the useful draft but explicitly label playback unverified and provide exact click cues. Do not claim compatibility or user acceptance without evidence.

Deliver the PPTX plus a concise click guide and relevant limitation. Keep storyboard, motion plan, resource/source list and build steps with the project so subsequent changes can be rebuilt. Record output SHA-256 and actual playback scope in a separate validation record, not speaker notes. Avoid misleading Final/Reviewed names for unverified versions.
