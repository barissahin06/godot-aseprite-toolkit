extends SceneTree


func _initialize() -> void:
	call_deferred("capture")


func capture() -> void:
	var args := OS.get_cmdline_user_args()
	assert(args.size() == 7)
	var packed := load(args[0]) as PackedScene
	assert(packed != null)
	var duration := float(args[3])
	var size: Array = JSON.parse_string(args[4])
	var output: String = args[5]
	var effects: Array = JSON.parse_string(args[6])
	root.size = Vector2i(int(size[0]), int(size[1]))
	root.content_scale_size = root.size
	RenderingServer.set_default_clear_color(Color("26232b"))
	var count := ceili(duration * 30.0)
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
			if not args[2].is_empty():
				var player := subject.get_node_or_null(NodePath(args[1])) as AnimationPlayer
				assert(player != null and player.has_animation(args[2]))
				player.play(args[2])
			for index: int in count:
				await process_frame
				RenderingServer.force_draw(false)
				var picture := root.get_texture().get_image()
				assert(picture.save_png(folder.path_join("%04d.png" % index)) == OK)
			holder.free()
	print("REVIEW_OK ", count * 4)
	quit()
