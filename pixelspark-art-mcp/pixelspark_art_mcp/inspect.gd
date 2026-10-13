extends SceneTree


func _initialize() -> void:
	call_deferred("inspect")


func inspect() -> void:
	var args := OS.get_cmdline_user_args()
	assert(args.size() == 2)
	var scene: PackedScene = load(args[0])
	assert(scene != null)
	var subject := scene.instantiate()
	root.add_child(subject)
	var report := {"scene": args[0], "nodes": [], "animations": [], "errors": []}
	walk(subject, subject, report)
	var file := FileAccess.open(args[1], FileAccess.WRITE)
	assert(file != null)
	file.store_string(JSON.stringify(report, "  "))
	print("INSPECT_OK ", report.nodes.size(), " nodes")
	subject.free()
	quit(0 if report.errors.is_empty() else 1)


func walk(node: Node, root_node: Node, report: Dictionary) -> void:
	var item := {"path": str(root_node.get_path_to(node)), "type": node.get_class()}
	if node is Bone2D:
		item.rest_determinant = node.rest.determinant()
		item.length = node.get_length()
		item.auto_length = node.get_autocalculate_length_and_angle()
		if absf(item.rest_determinant) < 0.001 or item.length <= 0:
			report.errors.append(item.path)
	report.nodes.append(item)
	if node is AnimationPlayer:
		for name in node.get_animation_list():
			var clip: Animation = node.get_animation(name)
			if not is_finite(clip.length) or clip.length <= 0:
				report.errors.append("Invalid clip length: " + str(name))
			var info := {
				"player": str(root_node.get_path_to(node)),
				"name": name,
				"seconds": clip.length,
				"loop": clip.loop_mode != Animation.LOOP_NONE,
				"tracks": [],
				"markers": {}
			}
			for marker in clip.get_marker_names():
				info.markers[marker] = clip.get_marker_time(marker)
			for i in clip.get_track_count():
				info.tracks.append(str(clip.track_get_path(i)))
				var target_path := clip.track_get_path(i)
				var base := node.get_node_or_null(node.root_node)
				if (
					base == null
					or base.get_node_or_null(NodePath(target_path.get_concatenated_names())) == null
				):
					report.errors.append("Missing animation target: " + str(target_path))
				for key: int in clip.track_get_key_count(i):
					var time := clip.track_get_key_time(i, key)
					if not is_finite(time) or time < 0 or time > clip.length:
						report.errors.append("Invalid key time: " + str(target_path))
			report.animations.append(info)
	for child in node.get_children():
		walk(child, root_node, report)
