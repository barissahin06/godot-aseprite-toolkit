extends SceneTree


func _initialize() -> void:
	call_deferred("capture")


func capture() -> void:
	var args := OS.get_cmdline_user_args()
	assert(args.size() == 8)
	var packed := load(args[0]) as PackedScene
	assert(packed != null)
	var duration := float(args[3])
	var size: Array = JSON.parse_string(args[4])
	var output: String = args[5]
	var effects: Array = JSON.parse_string(args[6])
	var fps: int = int(args[7])
	assert(fps >= 20 and fps <= 50)
	root.size = Vector2i(int(size[0]), int(size[1]))
	root.content_scale_size = root.size
	RenderingServer.set_default_clear_color(Color("26232b"))
	var count := ceili(duration * fps)
	var timeline: Dictionary = {"sampling": "engine_playback"}
	for mirrored: bool in [false, true]:
		for fx: bool in [false, true]:
			var mode := ("left" if mirrored else "right") + ("_fx" if fx else "_plain")
			var folder := output.path_join(mode)
			assert(DirAccess.make_dir_recursive_absolute(folder) == OK)
			var holder := Node2D.new()
			holder.position = Vector2(root.size) / 2.0
			holder.scale.x = -1.0 if mirrored else 1.0
			root.add_child(holder)
			var subject := packed.instantiate()
			holder.add_child(subject)
			for path: String in effects:
				var node := subject.get_node_or_null(NodePath(path)) as CanvasItem
				assert(node != null, "Unknown effect node")
				node.visible = fx
			var player: AnimationPlayer = null
			var clip: Animation = null
			if not args[2].is_empty():
				player = subject.get_node_or_null(NodePath(args[1])) as AnimationPlayer
				assert(player != null and player.has_animation(args[2]))
				clip = player.get_animation(args[2])
				player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
				player.stop()
				player.play(args[2])
				timeline = clip_timeline(clip, fps, count)
			for index: int in count:
				if player != null:
					# Advancing preserves method/event tracks as well as drawn frame keys.
					player.advance(0.0 if index == 0 else 1.0 / fps)
				# The node can hold the new pose while the viewport still holds the old image.
				await process_frame
				await RenderingServer.frame_post_draw
				var picture := root.get_texture().get_image()
				assert(picture.save_png(folder.path_join("%04d.png" % index)) == OK)
			holder.free()
	var metadata := FileAccess.open(output.path_join("timeline.json"), FileAccess.WRITE)
	assert(metadata != null)
	metadata.store_string(JSON.stringify(timeline, "  "))
	print("REVIEW_OK ", count * 4)
	quit()


static func sample_time(clip: Animation, seconds: float) -> float:
	if clip.loop_mode == Animation.LOOP_LINEAR:
		return fposmod(seconds, clip.length)
	if clip.loop_mode == Animation.LOOP_PINGPONG:
		var phase: float = fposmod(seconds, clip.length * 2.0)
		return phase if phase <= clip.length else clip.length * 2.0 - phase
	return minf(seconds, clip.length)


func clip_timeline(clip: Animation, fps: int, count: int) -> Dictionary:
	var info := {
		"sampling": "exact_animation_player",
		"seconds": clip.length,
		"loop": clip.loop_mode != Animation.LOOP_NONE,
		"loop_mode": clip.loop_mode,
		"markers": {},
		"frame_keys": [],
	}
	for marker: StringName in clip.get_marker_names():
		info.markers[marker] = clip.get_marker_time(marker)
	for track: int in clip.get_track_count():
		var path: NodePath = clip.track_get_path(track)
		if path.get_concatenated_subnames() != "frame":
			continue
		for key: int in clip.track_get_key_count(track):
			var start: float = clip.track_get_key_time(track, key)
			var end: float = (
				clip.track_get_key_time(track, key + 1)
				if key + 1 < clip.track_get_key_count(track)
				else clip.length
			)
			var samples: Array[int] = []
			for index: int in count:
				var time: float = sample_time(clip, float(index) / fps)
				if (
					time >= start - 0.000001
					and (
						time < end - 0.000001
						or (key + 1 == clip.track_get_key_count(track) and time <= end)
					)
				):
					samples.append(index)
			(
				info
				. frame_keys
				. append(
					{
						"track": str(path),
						"time": start,
						"seconds": end - start,
						"frame": clip.track_get_key_value(track, key),
						"captured_samples": samples,
					}
				)
			)
	return info
