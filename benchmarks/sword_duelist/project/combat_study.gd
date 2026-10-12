extends Node2D

const ANCHOR: Vector2 = Vector2(44, 70)
@export var asset_id: String = "combat_study"
@export var flow: bool = false
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
	var packed: PackedScene = load("res://assets/%s/%s.tscn" % [asset_id, asset_id])
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
	var player: AnimationPlayer = actors[0].get_node("AnimationPlayer")
	var attack: Animation = player.get_animation("attack")
	var attack_start: float = 1.04 if flow else 1.2
	var attack_end: float = attack_start + attack.length
	var cycle: float = attack_end + 0.1 if flow else 2.4
	phase = fposmod(seconds, cycle)
	active_clip = &"ready"
	clip_time = 0.0
	if phase < 0.96 - 0.00001:
		active_clip = &"walk"
		clip_time = phase
	elif phase >= attack_start - 0.00001 and phase < attack_end - 0.00001:
		active_clip = &"attack"
		clip_time = maxf(0.0, phase - attack_start)
	distance = mini(24, floori(phase / 0.04 + 0.00001)) * 2
	var origin_x: float = 48.0 - ANCHOR.x
	var offset := Vector2(-origin_x if mirrored else origin_x, 40 - ANCHOR.y)
	var origins: Array[Vector2] = [Vector2(148, 230), Vector2(450, 256)]
	for index: int in actors.size():
		var actor: Node2D = actors[index]
		var sprite: AnimatedSprite2D = actor.get_node(asset_id)
		var actor_player: AnimationPlayer = actor.get_node("AnimationPlayer")
		sprite.flip_h = mirrored
		actor.position = origins[index] + offset * actor.scale.x
		actor_player.play(active_clip)
		actor_player.seek(clip_time, true)
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
	var attack_start: float = 1.04 if flow else 1.2
	var cycle: float = attack_start + clip.length + 0.1 if flow else 2.4
	for marker: StringName in clip.get_marker_names():
		var x: float = 20 + (attack_start + clip.get_marker_time(marker)) / cycle * 600
		draw_line(Vector2(x, 303), Vector2(x, 318), Color("e4a34d"), 2.0)
	draw_line(Vector2(20, 310), Vector2(620, 310), ink.darkened(0.5), 1.0)
	draw_circle(Vector2(20 + phase / cycle * 600, 310), 3, ink)
	draw_string(
		font,
		Vector2(20, 343),
		(
			"Single attack / %.3f s / contact %.3f / chain ready %.3f"
			% [clip.length, clip.get_marker_time(&"contact"), clip.get_marker_time(&"chain_ready")]
		),
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		12,
		ink
	)
