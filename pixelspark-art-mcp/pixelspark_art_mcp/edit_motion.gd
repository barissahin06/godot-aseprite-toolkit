extends SceneTree


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	assert(args.size() == 4)
	var library := (
		ResourceLoader.load(args[0], "", ResourceLoader.CACHE_MODE_IGNORE) as AnimationLibrary
	)
	assert(library != null and library.has_animation(args[1]), "Unknown library/clip")
	var clip := library.get_animation(args[1])
	var patch: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[2]))
	assert(patch is Dictionary)
	for key: String in patch:
		assert(key in ["length", "loop", "tracks", "markers"], "Unknown patch field")
	if patch.has("length"):
		assert(patch.length is float or patch.length is int)
		assert(is_finite(float(patch.length)) and float(patch.length) > 0)
		clip.length = float(patch.length)
	if patch.has("loop"):
		assert(patch.loop is bool)
		clip.loop_mode = Animation.LOOP_LINEAR if patch.loop else Animation.LOOP_NONE
	assert(patch.get("tracks", []) is Array)
	for track: Dictionary in patch.get("tracks", []):
		assert(track.get("path") is String and not track.path.is_empty())
		for key: String in track:
			assert(key in ["path", "keys", "remove_keys", "interpolation"])
		var index := clip.find_track(NodePath(track.path), Animation.TYPE_VALUE)
		if index < 0:
			index = clip.add_track(Animation.TYPE_VALUE)
			clip.track_set_path(index, NodePath(track.path))
		if track.has("interpolation"):
			assert(track.interpolation in ["linear", "nearest", "cubic"])
			clip.track_set_interpolation_type(
				index,
				{
					"linear": Animation.INTERPOLATION_LINEAR,
					"nearest": Animation.INTERPOLATION_NEAREST,
					"cubic": Animation.INTERPOLATION_CUBIC
				}[track.interpolation]
			)
		for time: float in track.get("remove_keys", []):
			var existing := clip.track_find_key(index, time, Animation.FIND_MODE_EXACT)
			if existing >= 0:
				clip.track_remove_key(index, existing)
		for key: Array in track.get("keys", []):
			assert(key.size() == 2 and (key[0] is float or key[0] is int))
			var time := float(key[0])
			assert(is_finite(time) and time >= 0 and time <= clip.length)
			var value: Variant = key[1]
			if value is Array:
				assert(value.size() == 2)
				assert(value[0] is float or value[0] is int)
				assert(value[1] is float or value[1] is int)
				assert(
					value.size() == 2 and is_finite(float(value[0])) and is_finite(float(value[1]))
				)
				value = Vector2(float(value[0]), float(value[1]))
			elif value is float:
				assert(is_finite(value))
			clip.track_insert_key(index, time, value)
	assert(patch.get("markers", {}) is Dictionary)
	var markers: Dictionary = {}
	for name: StringName in clip.get_marker_names():
		markers[str(name)] = clip.get_marker_time(name)
	for name: String in patch.get("markers", {}):
		assert(not name.is_empty())
		var value: Variant = patch.markers[name]
		if value == null:
			markers.erase(name)
		else:
			assert(value is int or value is float)
			assert(is_finite(float(value)) and float(value) >= 0 and float(value) <= clip.length)
			markers[name] = float(value)
	var used_times: Array[float] = []
	for name: String in markers:
		var time := float(markers[name])
		assert(time <= clip.length)
		for previous: float in used_times:
			assert(not is_equal_approx(time, previous), "Marker time collision")
		used_times.append(time)
	for name: StringName in clip.get_marker_names():
		clip.remove_marker(name)
	for name: String in markers:
		clip.add_marker(name, float(markers[name]))
	for index: int in clip.get_track_count():
		for key: int in clip.track_get_key_count(index):
			assert(
				clip.track_get_key_time(index, key) <= clip.length,
				"Length would truncate existing keys"
			)
	assert(ResourceSaver.save(library, args[3]) == OK)
	print("MOTION_EDIT_OK")
	quit()
