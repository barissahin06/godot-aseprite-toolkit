extends SceneTree


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	assert(args.size() == 2)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var library := AnimationLibrary.new()
	for spec: Dictionary in data.clips:
		var clip := Animation.new()
		clip.resource_scene_unique_id = "clip_" + str(library.get_animation_list().size())
		clip.length = spec.seconds
		clip.loop_mode = Animation.LOOP_LINEAR if spec.loop else Animation.LOOP_NONE
		var tag_track: int = clip.add_track(Animation.TYPE_VALUE)
		clip.track_set_path(tag_track, NodePath(data.node + ":animation"))
		clip.value_track_set_update_mode(tag_track, Animation.UPDATE_DISCRETE)
		clip.track_insert_key(tag_track, 0.0, StringName(spec.name))
		var frame_track: int = clip.add_track(Animation.TYPE_VALUE)
		clip.track_set_path(frame_track, NodePath(data.node + ":frame"))
		clip.value_track_set_update_mode(frame_track, Animation.UPDATE_DISCRETE)
		var elapsed: float = 0.0
		for index: int in spec.durations.size():
			clip.track_insert_key(frame_track, elapsed, index)
			elapsed += spec.durations[index]
		for marker: String in spec.markers:
			clip.add_marker(marker, spec.markers[marker])
		assert(library.add_animation(spec.name, clip) == OK)
	assert(ResourceSaver.save(library, args[1]) == OK)
	print("FRAME_ANIMATIONS_OK ", library.get_animation_list().size())
	quit()
