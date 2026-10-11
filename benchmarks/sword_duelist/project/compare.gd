extends Node2D

const ROUTES: Array[String] = ["aseprite", "blender"]
const CLIPS: Array[String] = ["idle", "walk", "attack"]
const ANCHOR: Vector2 = Vector2(44, 70)
const CYCLE: float = 0.96
var subjects: Array[AnimatedSprite2D] = []
var elapsed: float = 0.0
var light_background: bool = false


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	for row: int in ROUTES.size():
		var frames := load("res://assets/%s/duelist.tres" % ROUTES[row]) as SpriteFrames
		assert(frames != null)
		for column: int in CLIPS.size():
			assert(frames.has_animation(CLIPS[column]))
			var sprite := AnimatedSprite2D.new()
			sprite.sprite_frames = frames
			sprite.animation = CLIPS[column]
			sprite.position = (
				Vector2(100 + 200 * column, 140 + 142 * row) + Vector2(48, 40) - ANCHOR
			)
			add_child(sprite)
			subjects.append(sprite)
	set_review_time(0.0)


func _process(delta: float) -> void:
	elapsed += delta
	set_review_time(elapsed)


func set_review_time(seconds: float) -> void:
	var cycle_time: float = fposmod(seconds, CYCLE)
	for sprite: AnimatedSprite2D in subjects:
		var frames := sprite.sprite_frames
		var clip: StringName = sprite.animation
		var time_left: float = cycle_time
		var count: int = frames.get_frame_count(clip)
		var index: int = 0
		while index < count - 1:
			var duration: float = (
				frames.get_frame_duration(clip, index) / frames.get_animation_speed(clip)
			)
			if time_left < duration - 0.000001:
				break
			time_left -= duration
			index += 1
		# A single attack ends at 0.70s; hold its recovery for the remaining 0.26s.
		sprite.frame = index


func set_view(light: bool, mirrored: bool) -> void:
	light_background = light
	for index: int in subjects.size():
		var sprite := subjects[index]
		sprite.flip_h = mirrored
		var origin: float = 48.0 - ANCHOR.x
		sprite.position.x = 100 + 200 * (index % CLIPS.size()) + (-origin if mirrored else origin)
	queue_redraw()


func _draw() -> void:
	var background := Color("9ca099") if light_background else Color("202333")
	var ink := Color("252839") if light_background else Color("e6dfbc")
	var font: Font = ThemeDB.fallback_font
	draw_rect(Rect2(0, 0, 640, 360), background)
	draw_string(
		font,
		Vector2(28, 28),
		"ASHGUARD / SAME SIZE, PALETTE AND TIMING",
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		14,
		ink
	)
	for row: int in ROUTES.size():
		for column: int in CLIPS.size():
			var x: float = 28 + 200 * column
			var y: float = 55 + 142 * row
			draw_string(
				font,
				Vector2(x, y),
				"%s / %s" % [ROUTES[row].to_upper(), CLIPS[column]],
				HORIZONTAL_ALIGNMENT_LEFT,
				-1,
				12,
				ink
			)
			draw_line(
				Vector2(x, 140 + 142 * row),
				Vector2(x + 145, 140 + 142 * row),
				ink.darkened(0.5),
				1.0
			)
	draw_string(
		font,
		Vector2(28, 331),
		"Native pixels / 30 fps review / attack includes a recovery hold",
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		12,
		ink
	)
