extends Node2D

const ANCHOR: Vector2 = Vector2(44, 70)
var actors: Array[Node2D] = []
var elapsed: float = 0.0
var phase: float = 0.0
var distance: float = 0.0
var light_background: bool = false
var mirrored: bool = false
var active_clip: StringName = &"walk"
var clip_time: float = 0.0


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	var packed: PackedScene = load("res://assets/combat_study/combat_study.tscn")
	for scale_factor: int in [1, 3]:
		var actor: Node2D = packed.instantiate()
		actor.scale = Vector2.ONE * scale_factor
		add_child(actor)
		actor.process_mode = Node.PROCESS_MODE_DISABLED
		actors.append(actor)
	set_review_time(0.0)


func _process(delta: float) -> void:
	elapsed += delta
	set_review_time(elapsed)


func set_review_time(seconds: float) -> void:
	phase = fposmod(seconds, 2.4)
	active_clip = &"ready"
	clip_time = 0.0
	if phase < 0.96 - 0.00001:
		active_clip = &"walk"
		clip_time = phase
	elif phase >= 1.2 - 0.00001 and phase < 1.92 - 0.00001:
		active_clip = &"attack"
		clip_time = maxf(0.0, phase - 1.2)
	distance = mini(24, floori(phase / 0.04 + 0.00001)) * 2
	var origin_x: float = 48.0 - ANCHOR.x
	var offset := Vector2(-origin_x if mirrored else origin_x, 40 - ANCHOR.y)
	var origins: Array[Vector2] = [Vector2(148, 230), Vector2(450, 256)]
	for index: int in actors.size():
		var actor: Node2D = actors[index]
		var sprite: AnimatedSprite2D = actor.get_node("combat_study")
		var player: AnimationPlayer = actor.get_node("AnimationPlayer")
		sprite.flip_h = mirrored
		actor.position = origins[index] + offset * actor.scale.x
		player.play(active_clip)
		player.seek(clip_time, true)
	queue_redraw()


func set_view(light: bool, face_left: bool) -> void:
	light_background = light
	mirrored = face_left
	set_review_time(elapsed)


func _draw() -> void:
	var background := Color("9ca099") if light_background else Color("202333")
	var ink := Color("252839") if light_background else Color("e6dfbc")
	var font: Font = ThemeDB.fallback_font
	draw_rect(Rect2(0, 0, 640, 360), background)
	draw_string(
		font,
		Vector2(20, 28),
		"ASEPRITE / WALK > READY > STRIKE > READY",
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		14,
		ink
	)
	draw_string(
		font, Vector2(28, 65), "Native / " + active_clip, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, ink
	)
	draw_string(font, Vector2(315, 65), "Nearest 3x", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, ink)
	for index: int in actors.size():
		var y: float = 230 if index == 0 else 256
		var left: float = 28 if index == 0 else 306
		var right: float = 268 if index == 0 else 615
		var factor: float = 1 if index == 0 else 3
		draw_line(Vector2(left, y), Vector2(right, y), ink.darkened(0.5), 1.0)
		var x: float = left + fposmod(distance * factor * (1 if mirrored else -1), 24 * factor)
		while x < right:
			if x >= left:
				draw_line(Vector2(x, y + 2), Vector2(x, y + 5), ink.darkened(0.5), 1.0)
			x += 24 * factor
	var player: AnimationPlayer = actors[0].get_node("AnimationPlayer")
	var clip: Animation = player.get_animation("attack")
	for marker: StringName in clip.get_marker_names():
		var x: float = 20 + (1.2 + clip.get_marker_time(marker)) / 2.4 * 600
		draw_line(Vector2(x, 303), Vector2(x, 318), Color("e4a34d"), 2.0)
	draw_line(Vector2(20, 310), Vector2(620, 310), ink.darkened(0.5), 1.0)
	draw_circle(Vector2(20 + phase / 2.4 * 600, 310), 3, ink)
	draw_string(
		font,
		Vector2(20, 343),
		"Single attack / 0.72 s / contact 0.28 / chain ready 0.54",
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		12,
		ink
	)
