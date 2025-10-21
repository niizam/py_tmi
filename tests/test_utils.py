from py_tmi import utils


def test_channel_normalization():
    assert utils.channel("Example") == "#example"
    assert utils.channel("#Already") == "#already"


def test_username_normalization():
    assert utils.username("Example") == "example"
    assert utils.username("#Nick") == "nick"


def test_paginate_message_respects_limit():
    message = " ".join(["word"] * 200)
    chunks = list(utils.paginate_message(message, limit=50))
    assert all(len(chunk) <= 50 for chunk in chunks)
    assert "word" in chunks[0]
