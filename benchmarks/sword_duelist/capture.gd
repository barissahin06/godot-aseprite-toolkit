extends SceneTree


func _initialize() -> void:
	call_deferred("capture")


func capture() -> void:
	var args := OS.get_cmdline_user_args()
	assert(args.size() == 2)
	var output: String = args[0]
	var count: int = int(args[1])
	assert(count > 0 and count <= 300)
	root.size = Vector2i(640, 360)
	root.content_scale_size = root.size
	var packed := load("res://compare.tscn") as PackedScene
	assert(packed != null)
	for light: bool in [false, true]:
		for mirrored: bool in [false, true]:
			var mode := ("light" if light else "dark") + ("_left" if mirrored else "_right")
			var folder: String = output.path_join(mode)
			assert(DirAccess.make_dir_recursive_absolute(folder) == OK)
			var subject := packed.instantiate() as Node2D
			root.add_child(subject)
			subject.set_process(false)
			subject.set_view(light, mirrored)
			for index: int in count:
				subject.set_review_time(float(index) / 30.0)
				await process_frame
				RenderingServer.force_draw(false)
				var picture: Image = root.get_texture().get_image()
				assert(picture.save_png(folder.path_join("%04d.png" % index)) == OK)
			subject.free()
	print("COMPARISON_OK ", count * 4)
	quit()
