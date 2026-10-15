# GameLink Agent — headless project introspection (dev_plan_1.md §4.5).
#
# Run:  godot --headless --path <project> --script res://_gamelink_introspect.gd
# Emits a single machine-readable line prefixed with GAMELINK_FACTS_JSON.
extends SceneTree

const MARKER := "GAMELINK_FACTS_JSON"


func _init() -> void:
	var facts := {
		"autoloads": _collect_autoloads(),
		"rpc_methods": _scan_dir("res://"),
		"synchronizers": [],
		"spawners": [],
	}
	print(MARKER + ": " + JSON.stringify(facts))
	quit()


func _collect_autoloads() -> Array:
	var out: Array = []
	for prop in ProjectSettings.get_property_list():
		var prop_name: String = prop.get("name", "")
		if prop_name.begins_with("autoload/"):
			out.append(prop_name.substr("autoload/".length()))
	return out


func _scan_dir(path: String) -> Array:
	var out: Array = []
	var dir := DirAccess.open(path)
	if dir == null:
		return out
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		if name.begins_with("."):
			name = dir.get_next()
			continue
		var full := path.path_join(name)
		if dir.current_is_dir():
			out.append_array(_scan_dir(full))
		elif name.ends_with(".gd"):
			out.append_array(_scan_script(full))
		name = dir.get_next()
	dir.list_dir_end()
	return out


func _scan_script(res_path: String) -> Array:
	var out: Array = []
	var file := FileAccess.open(res_path, FileAccess.READ)
	if file == null:
		return out
	var pending := false
	for line in file.get_as_text().split("\n"):
		var stripped := line.strip_edges()
		if stripped.begins_with("@rpc"):
			pending = true
			continue
		if pending and stripped.begins_with("func "):
			var signature := stripped.substr(5)
			out.append({"script": res_path, "name": signature.split("(")[0].strip_edges()})
			pending = false
	return out
