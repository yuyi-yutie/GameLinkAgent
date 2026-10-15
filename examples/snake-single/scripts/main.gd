extends Node2D

## Single-player Snake game controller.
##
## Responsibilities mixed together here (the thing GameLink Agent will untangle):
##   - authoritative state: snake movement, food placement, eating, scoring, game over
##   - client presentation: input capture, rendering, score label
##
## After 联机化, movement/eating/scoring move to the server; input becomes an RPC
## intent and rendering stays on the client.

const GRID_SIZE := 20
const CELL := 32

@onready var score_label: Label = $UI/ScoreLabel

var snake: Snake
var food := Vector2i.ZERO
var score := 0
var move_interval := 0.15
var accumulator := 0.0
var game_over := false


func _ready() -> void:
	randomize()
	_restart()


func _unhandled_input(event: InputEvent) -> void:
	if game_over:
		if event is InputEventKey and event.pressed and event.keycode == KEY_R:
			_restart()
		return
	if event.is_action_pressed("ui_up"):
		snake.set_direction(Vector2i.UP)
	elif event.is_action_pressed("ui_down"):
		snake.set_direction(Vector2i.DOWN)
	elif event.is_action_pressed("ui_left"):
		snake.set_direction(Vector2i.LEFT)
	elif event.is_action_pressed("ui_right"):
		snake.set_direction(Vector2i.RIGHT)


func _process(delta: float) -> void:
	if game_over:
		return
	accumulator += delta
	while accumulator >= move_interval:
		accumulator -= move_interval
		_step()
	queue_redraw()


func _step() -> void:
	var next := snake.next_cell()
	if next.x < 0 or next.y < 0 or next.x >= GRID_SIZE or next.y >= GRID_SIZE:
		_end_game()
		return
	if next in snake.body_without_head():
		_end_game()
		return
	var ate := next == food
	snake.advance(ate)
	if ate:
		score += 1
		_update_score()
		_spawn_food()


func _spawn_food() -> void:
	var free: Array[Vector2i] = []
	for x in GRID_SIZE:
		for y in GRID_SIZE:
			if not snake.occupies(Vector2i(x, y)):
				free.append(Vector2i(x, y))
	if free.is_empty():
		_end_game()
		return
	food = free[randi() % free.size()]


func _end_game() -> void:
	game_over = true
	score_label.text = "Game Over - Score: %d (press R)" % score


func _update_score() -> void:
	score_label.text = "Score: %d" % score


func _restart() -> void:
	snake = Snake.new()
	score = 0
	accumulator = 0.0
	game_over = false
	_update_score()
	_spawn_food()
	queue_redraw()


func _draw() -> void:
	draw_rect(
		Rect2(Vector2.ZERO, Vector2(GRID_SIZE * CELL, GRID_SIZE * CELL)),
		Color(0.1, 0.1, 0.12)
	)
	draw_rect(Rect2(Vector2(food) * CELL, Vector2(CELL, CELL)), Color(0.9, 0.3, 0.3))
	for i in snake.segments.size():
		var color := Color(0.4, 0.85, 0.4) if i == 0 else Color(0.25, 0.6, 0.3)
		draw_rect(Rect2(Vector2(snake.segments[i]) * CELL, Vector2(CELL, CELL)), color)
