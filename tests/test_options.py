from gamelink.options import OPTION_CHOICES, DesignerOptions


def test_defaults():
    options = DesignerOptions()
    assert options.transport == "enet"
    assert options.max_players == 4
    assert options.tick_rate == 15


def test_to_dict_roundtrip():
    options = DesignerOptions(transport="websocket", max_players=8)
    restored = DesignerOptions.from_dict(options.to_dict())
    assert restored == options


def test_from_dict_ignores_unknown_keys():
    options = DesignerOptions.from_dict({"transport": "webrtc", "bogus": 1})
    assert options.transport == "webrtc"
    assert not hasattr(options, "bogus")


def test_every_choice_is_a_valid_default_family():
    assert set(OPTION_CHOICES) <= set(DesignerOptions().to_dict())
