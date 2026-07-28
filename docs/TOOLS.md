# Tool reference

All indices are 1-based unless a parameter explicitly says frame offset.
Mutating tools raise a failed MCP result when Resolve rejects the action.

## Inspect and timeline

`connect_to_resolve`, `current_project`, `current_timeline`, `list_timelines`,
`switch_timeline`, `list_clips`, `current_playhead`, `jump_to_timecode`,
`current_clip`, `inspect_clip`, `selected_clips`, `inspect_media_pool`,
`search_clips`, and `batch_rename_clips`.

`selected_clips` means Media Pool selection. Resolve does not expose timeline
multi-selection.

## Markers

`list_markers`, `add_marker`, `delete_marker`, and `jump_marker`. Marker frames
are offsets from the timeline start.

## Nodes and grades

`inspect_node_tree`, `list_nodes`, `set_node_enabled`, `set_cdl`, `copy_grade`,
`apply_grade`, `register_powergrade`, `search_powergrades`, `load_powergrade`,
`batch_grade_clips`, and the six `create_*_grade` workflow tools.

`add_serial_node`, `add_parallel_node`, `add_layer_mixer`, and `label_node`
exist as capability-reporting tools so an agent learns the correct DRX route.
`analyze_clip_scopes` similarly documents unavailable numerical image analysis.

## Render

`list_render_presets`, `create_render_preset`, `add_render_job`,
`list_render_jobs`, `start_render`, and `monitor_render`.

Use the format/codec identifiers returned by Resolve, not display-name guesses.
For common H.264, ProRes, and DNxHR output, save a known-good Resolve preset and
pass its name to `add_render_job`; codec availability varies by platform/version.

## Gallery

`list_gallery_albums`, `list_stills`, `save_powergrade`, and `export_still`.
Export a Gallery still as DRX before applying it through `apply_grade`.
