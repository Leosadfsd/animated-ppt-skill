# Motion manifest

UTF-8 JSON, slide numbers refer to presentation order (not slide filenames):

```json
{
  "version": 1,
  "slides": [
    {"slide": 1, "units": [
      {"name": "title", "beat": 0, "from": "top", "delay_ms": 0, "duration_ms": 750},
      {"name": "portrait", "beat": 1, "from": "left", "delay_ms": 0, "duration_ms": 750},
      {"name": "caption-group", "beat": 1, "from": "bottom", "delay_ms": 300, "duration_ms": 750}
    ]}
  ]
}
```

Each name must uniquely identify an exported top-level shape, picture or native group. Inspect the draft to find actual names. Backgrounds and other unlisted objects remain unchanged. A native group moves rigidly; independently animated children are intentionally unsupported to avoid ambiguous transforms.

Beats are nonnegative integers. Positive beats must be contiguous starting at 1; beat 0 is optional. Delay is a nonnegative integer measured from the beat start. Duration is a positive integer. Units in a beat sort by delay, preserving input order for ties. Edges: left, right, top, bottom. Use brief delays chosen for the narration rather than generating excessive clicks.

The timing uses native fly-in presets, visibility sets and normalized ppt_x/ppt_y formulas. It does not add an explicit hidden flag to the final static shape; the viewer's entrance-animation engine handles pre-entrance visibility. Actual viewer playback must verify this. Native groups, imported media and fonts can behave differently between viewers.

Only slides listed in the manifest receive timing changes. No media, notes, layout, geometry or shape IDs are changed. Existing timing requires explicit replacement. Keep motion files free of absolute paths and private manuscript content when publishing examples.
