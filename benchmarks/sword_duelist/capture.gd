extends SceneTree


func _initialize() -> void:
	call_deferred("capture")


func capture() -> void:
	var args := OS.get_cmdline_user_args()
	assert(args.size() >= 2 and args.size() <= 4)
	var output: String = args[0]
	var count: int = int(args[1])
	var fps: int = int(args[3]) if args.size() == 4 else 30
	assert(count > 0 and count <= 300)
	assert(fps >= 20 and fps <= 60)
	root.size = Vector2i(640, 360)
	root.content_scale_size = root.size
	var scene: String = args[2] if args.size() >= 3 else "res://compare.tscn"
	var packed := load(scene) as PackedScene
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
				subject.set_review_time(float(index) / float(fps))
				await process_frame
				RenderingServer.force_draw(false)
				var picture: Image = root.get_texture().get_image()
				assert(picture.save_png(folder.path_join("%04d.png" % index)) == OK)
			subject.free()
	print("COMPARISON_OK ", count * 4)
	quit()
