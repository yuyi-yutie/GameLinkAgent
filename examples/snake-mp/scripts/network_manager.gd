extends Node

## Autoload: owns the ENet peer and exposes host/join.
## Deliberately thin — lobby/world logic lives in the main scene.

signal session_started(is_server: bool)

const DEFAULT_PORT := 7000
const MAX_PLAYERS := 8

var peer: MultiplayerPeer


func host(port: int = DEFAULT_PORT) -> Error:
	var server := ENetMultiplayerPeer.new()
	var err := server.create_server(port, MAX_PLAYERS)
	if err != OK:
		push_error("failed to start server on port %d (error %d)" % [port, err])
		return err
	peer = server
	multiplayer.multiplayer_peer = server
	session_started.emit(true)
	return OK


func join(address: String, port: int = DEFAULT_PORT) -> Error:
	var client := ENetMultiplayerPeer.new()
	var err := client.create_client(address, port)
	if err != OK:
		push_error("failed to connect to %s:%d (error %d)" % [address, port, err])
		return err
	peer = client
	multiplayer.multiplayer_peer = client
	session_started.emit(false)
	return OK
