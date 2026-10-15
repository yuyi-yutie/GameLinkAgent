class_name Snake
extends RefCounted

## Grid-based snake entity. Holds authoritative state only; rendering and input
## live in the game controller. This separation is what makes it easy for
## GameLink Agent to move this logic to the server later.

var segments: Array[Vector2i]
var direction: Vector2i = Vector2i.RIGHT
var pending_direction: Vector2i = Vector2i.RIGHT


func _init(start: Vector2i = Vector2i(5, 10), length: int = 3) -> void:
	segments = []
	for i in length:
		segments.append(start + Vector2i.LEFT * i)


func head() -> Vector2i:
	return segments[0]


func next_cell() -> Vector2i:
	return head() + pending_direction


func set_direction(dir: Vector2i) -> void:
	if dir != -direction:
		pending_direction = dir


func advance(grow: bool) -> void:
	direction = pending_direction
	segments.insert(0, head() + direction)
	if not grow:
		segments.pop_back()


func occupies(cell: Vector2i) -> bool:
	return cell in segments


func body_without_head() -> Array[Vector2i]:
	if segments.is_empty():
		return []
	return segments.slice(0, segments.size() - 1)
