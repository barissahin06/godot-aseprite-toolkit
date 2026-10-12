extends SceneTree


func _initialize() -> void:
	call_deferred("check_review")


func check_review() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var helper: GDScript = load(args[2])
	var timing := Animation.new()
	timing.length = 0.12
	assert(is_equal_approx(helper.sample_time(timing, 0.18), 0.12))
	timing.loop_mode = Animation.LOOP_LINEAR
	assert(is_equal_approx(helper.sample_time(timing, 0.18), 0.06))
	timing.loop_mode = Animation.LOOP_PINGPONG
	assert(is_equal_approx(helper.sample_time(timing, 0.18), 0.06))
	assert(is_equal_approx(helper.sample_time(timing, 0.24), 0.0))
	var packed: PackedScene = load(args[0])
	var subject: Node = packed.instantiate()
	root.add_child(subject)
	var sprite: AnimatedSprite2D = subject.get_node("example_fx")
	var background := Color("26232b")
	var checked: int = 0
	for sample: int in 18:
		var expected: Image = (
			sprite.sprite_frames.get_frame_texture("default", sample / 6).get_image()
		)
		var actual := Image.load_from_file(args[1].path_join("right_fx/%04d.png" % sample))
		var origin := (actual.get_size() - expected.get_size()) / 2
		for y: int in expected.get_height():
			for x: int in expected.get_width():
				var pixel: Color = expected.get_pixel(x, y)
				var composite: Color = background.blend(pixel)
				var captured: Color = actual.get_pixel(origin.x + x, origin.y + y)
				if (
					absf(captured.r - composite.r) > 1.0 / 255
					or absf(captured.g - composite.g) > 1.0 / 255
					or absf(captured.b - composite.b) > 1.0 / 255
				):
					push_error("Native review pixels differ at sample " + str(sample))
					subject.free()
					quit(1)
					return
				checked += 1
	assert(checked > 0)
	subject.free()
	print("REVIEW_PLAYBACK_OK ", checked, " pixels; time zero and every frame boundary")
	quit()
