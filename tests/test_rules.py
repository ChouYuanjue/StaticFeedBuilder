from feed_builder.text_rules import infer_from_text


def test_infer_online_ai():
    text = "This online challenge allows pretrained models and external data. Submission deadline: 2026-08-01. No registration fee."
    data = infer_from_text(text)
    assert data["mode"] == "online"
    assert data["ai_policy"] == "allowed"
    assert data["fee"] == "free"
    assert data["dates"]

