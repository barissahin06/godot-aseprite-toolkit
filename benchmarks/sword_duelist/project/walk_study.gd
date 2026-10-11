extends Node2D

const ANCHOR: Vector2 = Vector2(44, 70)
const FRAME_SECONDS: float = 0.04
const STEP_PIXELS: int = 2
var subjects: Array[AnimatedSprite2D] = []
var elapsed: float = 0.0
var distance: float = 0.0
var light_background: bool = false
var mirrored: bool = false


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	var frames := load("res://assets/walk_study/walk_study.tres") as SpriteFrames
	assert(frames != null and frames.get_frame_count("walk") == 24)
	for scale_factor: int in [1, 3, 1]:
		var sprite := AnimatedSprite2D.new()
		sprite.sprite_frames = frames
		sprite.animation = &"walk"
		sprite.scale = Vector2.ONE * scale_factor
		add_child(sprite)
		subjects.append(sprite)
	set_review_time(0.0)


func _process(delta: float) -> void:
	elapsed += delta
	set_review_time(elapsed)


func set_review_time(seconds: float) -> void:
	var step: int = floori(seconds / FRAME_SECONDS + 0.00001)
	distance = (step % 192) * STEP_PIXELS
	var origin_x: float = 48.0 - ANCHOR.x
	var offset := Vector2(-origin_x if mirrored else origin_x, 40 - ANCHOR.y)
	var world_x: float = 580.0 - distance if mirrored else 60.0 + distance
	var origins: Array[Vector2] = [Vector2(148, 230), Vector2(450, 256), Vector2(world_x, 342)]
	for index: int in subjects.size():
		var sprite := subjects[index]
		sprite.frame = step % 24
		sprite.flip_h = mirrored
		sprite.position = origins[index] + offset * sprite.scale.x
	queue_redraw()


func set_view(light: bool, face_left: bool) -> void:
	light_background = light
	mirrored = face_left
	set_review_time(elapsed)


func floor_marks(
	left: float, right: float, y: float, scale_factor: float, moving: bool, ink: Color
) -> void:
	draw_line(Vector2(left, y), Vector2(right, y), ink, 1.0)
	var spacing: float = 24.0 * scale_factor
	var shift: float = (
		fposmod(distance * scale_factor * (1.0 if mirrored else -1.0), spacing) if moving else 0.0
	)
	var x: float = left + shift
	while x < right:
		if x >= left:
			draw_line(Vector2(x, y + 2), Vector2(x, y + 5), ink, 1.0)
		x += spacing


func _draw() -> void:
	var background := Color("9ca099") if light_background else Color("202333")
	var ink := Color("252839") if light_background else Color("e6dfbc")
	var font: Font = ThemeDB.fallback_font
	draw_rect(Rect2(0, 0, 640, 360), background)
	draw_string(
		font,
		Vector2(20, 28),
		"ASEPRITE / CONTROLLED WALK / 8 KEYS + 16 IN-BETWEENS",
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		14,
		ink
	)
	draw_string(
		font, Vector2(28, 65), "Native / moving ground", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, ink
	)
	draw_string(
		font, Vector2(315, 65), "Nearest 3x / moving ground", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, ink
	)
	draw_string(
		font,
		Vector2(20, 280),
		"World movement / authored root motion: 48 px per 0.96s",
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		12,
		ink
	)
	floor_marks(28, 268, 230, 1, true, ink.darkened(0.5))
	floor_marks(306, 615, 256, 3, true, ink.darkened(0.5))
	floor_marks(20, 620, 342, 1, false, ink.darkened(0.5))
