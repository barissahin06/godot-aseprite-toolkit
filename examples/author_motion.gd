extends SceneTree


func _initialize() -> void:
	var destination := "res://rig/motion.tres"
	if not FileAccess.file_exists(destination):
		DirAccess.make_dir_recursive_absolute("res://rig")
		var library := AnimationLibrary.new()
		for name: String in ["idle", "attack"]:
			var clip := Animation.new()
			clip.length = 0.6
			clip.loop_mode = Animation.LOOP_LINEAR if name == "idle" else Animation.LOOP_NONE
			var index := clip.add_track(Animation.TYPE_VALUE)
			clip.track_set_path(index, NodePath("Skeleton2D/root/body/weapon:rotation"))
			clip.track_insert_key(index, 0.0, -0.1)
			clip.track_insert_key(index, 0.3, 0.2 if name == "idle" else -1.0)
			clip.track_insert_key(index, 0.6, -0.1)
			clip.add_marker("contact", 0.3)
			clip.add_marker("chain_ready", 0.5)
			assert(library.add_animation(name, clip) == OK)
		assert(ResourceSaver.save(library, destination) == OK)
	print("EXAMPLE_MOTION_OK")
	quit()
