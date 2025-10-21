from py_tmi import parser


def test_parse_message_with_tags():
    raw = "@badge-info=subscriber/12;badges=subscriber/12;color=#1E90FF;tmi-sent-ts=1640995200000 :user!user@user PRIVMSG #channel :Hello World"
    message = parser.parse_message(raw)
    assert message is not None
    assert message.command == "PRIVMSG"
    assert message.prefix.startswith("user!")
    assert message.params[-1] == "Hello World"
    message.tags = parser.parse_badge_info(parser.parse_badges(message.tags))
    assert message.tags["badge-info"]["subscriber"] == "12"
    assert message.tags["badges"]["subscriber"] == "12"


def test_form_tags_roundtrip():
    tags = {"client-nonce": "abc123", "reply-parent-msg-id": "42"}
    encoded = parser.form_tags(tags)
    parsed = parser.parse_message(f"{encoded} PRIVMSG #chan :hello")
    assert parsed is not None
    for key, value in tags.items():
        assert parsed.tags[key] == value
