# Portable scene and click previews

Use `scene.py` when creating a new deck from a manuscript. For an existing PPTX, use `animate.py` and avoid rebuilding the whole file.

## Commands

Resolve the installed skill directory, then call its scripts by that path:

```sh
python <skill-dir>/scripts/scene.py doctor --font "Microsoft YaHei"
python <skill-dir>/scripts/scene.py validate scene.json
python <skill-dir>/scripts/scene.py build scene.json new-build-directory
```

`doctor` checks Python, Node, whether `@oai/artifact-tool` can actually import, and the optional requested font in the OS font inventory. It does not install packages or verify WPS/PowerPoint playback. On Codex Desktop, get current runtime paths from `load_workspace_dependencies`; set `RUNTIME_NODE` and `RUNTIME_NODE_MODULES` to the returned Node executable and node_modules directory. Otherwise an authoring package resolvable from the current project is supported. Never copy a runtime path from someone else's machine.

`build` refuses an existing directory. It validates the scene and asset paths, renders editable text and images, binds actual exported objects, creates native groups for multi-element units, injects animations, and writes cumulative static click previews. It fails on missing/ambiguous targets rather than selecting objects by creation order.

## Schema

```json
{
  "version": 1,
  "title": "Example talk",
  "width": 1280,
  "height": 720,
  "font": "Microsoft YaHei",
  "background": "#F5F1E8",
  "color": "#183C34",
  "slides": [{
    "title": "One idea",
    "notes": "The full manuscript passage for this slide.",
    "sources": ["Image provenance or source URL"],
    "units": [{
      "name": "caption",
      "beat": 1,
      "cue": "What the speaker says when clicking.",
      "from": "left",
      "delay_ms": 0,
      "duration_ms": 750,
      "elements": [
        {"type": "image", "src": "assets/paper.png", "frame": [500, 300, 620, 180], "fit": "contain"},
        {"type": "text", "text": "Editable caption", "frame": [550, 340, 500, 80], "size": 48, "bold": true, "align": "center"}
      ]
    }]
  }]
}
```

Geometry and numeric font sizes are CSS pixels at 96 DPI. Positive beats must be contiguous starting at 1, `0` is automatic, `-1` is always visible. Each native unit has one motion configuration and one or more elements. Multiple elements are grouped automatically, keeping text and its paper together. Units and elements are listed in back-to-front stacking order. Names are unique per slide and cannot contain `__` (reserved for internal element keys).

Text supports `text`, `frame`, `size`, `font`, `color`, `bold`, `italic`, `align` and `rotation`. Images support `src`, `frame`, `fit` and `rotation`. Image sources are relative, stay inside the scene directory, and must already exist. Prepare intentional complete bitmap assets; this renderer is not an illustration engine. Do not use it to draw decorative vector shapes. Different units can have staggered `delay_ms` within the same beat.

The exporter can omit image names/alt text. Binding first uses unique exported names, then a unique centered image frame matched against the scene when necessary. Multiple images sharing that frame are ambiguous and rejected; change the authoring structure rather than guessing. No object IDs or image order are assumed. Rotation bounds are included when grouping; independently rotated child elements retain their original transforms.

## Outputs and boundaries

- `animated.pptx`: structurally checked native animation output; actual playback initially unverified.
- `draft.pptx`, `grouped.pptx`, `motion.json`: editable intermediate/source mappings.
- `index.html`: offline clickable gallery with each node's screen and speaking cue.
- `click-guide.md`, `states.json`, `previews/`: portable cumulative static states and visible unit names.
- `environment.json`, `render.log`, `validation.json`: local debugging/validation records. The environment report contains local executable paths; exclude it from public distribution.

Previews show which content should be visible after a beat finishes. They do not simulate entrance movement, per-unit delays, clipping in motion, or viewer compatibility. Only target-software observation can validate those. Rendered previews come from the scene before native grouping; compare the grouped exported deck when verifying groups.

Changing text, assets, positions or cues normally requires editing only `scene.json`, then building a new revision. New scenes still require the AI to interpret the manuscript and design a suitable layout. This schema supports text/image layouts, not native charts/tables, nested groups, arbitrary motion paths or automatic semantic segmentation of an existing deck.
