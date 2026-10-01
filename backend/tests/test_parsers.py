from pathlib import Path

from app.parsers.concrete import WhatsAppParser


def test_whatsapp_parser(tmp_path: Path):
    f = tmp_path / "whatsapp.txt"
    f.write_text("12/09/2026, 09:10 - Riya: hello arjun@upi")
    events = WhatsAppParser().parse(f, case_id=1, evidence_id=2)
    assert len(events) == 1
    assert events[0].actor_entities == ["Riya"]
    assert "arjun@upi" in events[0].content


def test_whatsapp_parser_multiline_bracketed_and_system_messages(tmp_path: Path):
    f = tmp_path / "whatsapp_group.txt"
    f.write_text(
        "\n".join(
            [
                "[12/09/26, 9:10:32 AM] Riya: hello",
                "this is the second line",
                "[12/09/26, 9:11:00 AM] Arjun: <Media omitted>",
                "[12/09/26, 9:12:00 AM] Messages and calls are end-to-end encrypted.",
                "12/09/2026, 21:15 - Riya: रात को payment bheja",
            ]
        )
    )

    events = WhatsAppParser().parse(f, case_id=1, evidence_id=2)

    assert len(events) == 4
    assert events[0].action == "message"
    assert events[0].content == "hello\nthis is the second line"
    assert events[1].action == "media_omitted"
    assert events[1].actor_entities == ["Arjun"]
    assert events[2].action == "system_message"
    assert events[2].actor_entities == []
    assert events[3].content == "रात को payment bheja"
