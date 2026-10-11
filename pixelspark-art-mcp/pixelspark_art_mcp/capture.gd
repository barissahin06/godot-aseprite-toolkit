extends SceneTree


func _initialize() -> void:
	call_deferred("capture")


func capture() -> void:
	var args := OS.get_cmdline_user_args()
	assert(args.size() in [5, 6], "scene, player path, clip, times JSON, output directory")
	var scene: PackedScene = load(args[0])
	assert(scene != null)
	var subject := scene.instantiate()
	root.add_child(subject)
	subject.process_mode = Node.PROCESS_MODE_DISABLED
	var player: AnimationPlayer = subject.get_node_or_null(NodePath(args[1]))
	var times: Array = JSON.parse_string(args[3])
	var output: String = args[4]
	assert(DirAccess.make_dir_recursive_absolute(output) == OK)
	var size: Array = JSON.parse_string(args[5]) if args.size() == 6 else [640, 360]
	root.size = Vector2i(int(size[0]), int(size[1]))
	root.content_scale_size = root.size
	var sheet: Image
	for i in times.size():
		if not args[2].is_empty():
			assert(player != null and player.has_animation(args[2]), "Unknown player/clip")
			var clip := player.get_animation(args[2])
			assert(
				float(times[i]) >= 0 and float(times[i]) <= clip.length + 0.00001,
				"Time outside clip"
			)
			player.play(args[2])
			player.seek(minf(float(times[i]), clip.length), true)
		await process_frame
		# A stationary final pose may not schedule another redraw; request it explicitly.
		RenderingServer.force_draw(false)
		var picture := root.get_texture().get_image()
		assert(picture != null and not picture.is_empty(), "Render is empty")
		assert(picture.save_png(output.path_join("%03d.png" % i)) == OK)
		if i == 0:
			sheet = Image.create(
				picture.get_width() * mini(3, times.size()),
				picture.get_height() * ceili(times.size() / 3.0),
				false,
				picture.get_format()
			)
		sheet.blit_rect(
			picture,
			Rect2i(Vector2i.ZERO, picture.get_size()),
			Vector2i((i % 3) * picture.get_width(), floori(i / 3.0) * picture.get_height())
		)
	assert(sheet.save_png(output.path_join("contact-sheet.png")) == OK)
	print("CAPTURE_OK ", times.size())
	subject.free()
	quit()
