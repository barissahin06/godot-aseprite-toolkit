extends SceneTree


func _initialize() -> void:
	call_deferred("check_frames")


func check_frames() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var packed: PackedScene = load(args[0])
	var subject: Node = packed.instantiate()
	root.add_child(subject)
	var player: AnimationPlayer = subject.get_node("AnimationPlayer")
	var sprite: AnimatedSprite2D = subject.get_node("example_fx")
	assert(not sprite.is_playing())
	assert(not sprite.sprite_frames.get_animation_loop("default"))
	var clip: Animation = player.get_animation("default")
	assert(clip.loop_mode == Animation.LOOP_NONE)
	for sample: Array in [
		[0.0, 0], [0.06, 0], [0.12, 1], [0.22, 1], [0.24, 2], [0.359, 2], [0.5, 2]
	]:
		player.stop()
		player.play("default")
		player.advance(sample[0])
		assert(sprite.frame == sample[1], "Unexpected discrete frame at " + str(sample[0]))
	assert(not player.is_playing())
	subject.free()
	print("FRAME_PLAYBACK_OK")
	quit()
