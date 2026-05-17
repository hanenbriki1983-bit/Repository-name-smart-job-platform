import os

from main import _chatbot_reply


def _force_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_empty_message_returns_prompt(monkeypatch):
    _force_fallback(monkeypatch)
    assert _chatbot_reply("", None) == "Please type a message."


def test_english_fallback_reply_language(monkeypatch):
    _force_fallback(monkeypatch)
    reply = _chatbot_reply("Can you help me find a job?", None)
    assert isinstance(reply, str)
    assert len(reply.strip()) > 0
    assert any(token in reply.lower() for token in ["job", "jobs", "cv", "interview", "search"])


def test_german_fallback_reply_language(monkeypatch):
    _force_fallback(monkeypatch)
    reply = _chatbot_reply("Ich brauche Hilfe bei der Jobsuche", None)
    assert isinstance(reply, str)
    assert len(reply.strip()) > 0
    assert any(token in reply.lower() for token in ["ich", "hilfe", "jobsuche", "interview", "lebenslauf", "job"])


def test_arabic_fallback_reply_language(monkeypatch):
    _force_fallback(monkeypatch)
    reply = _chatbot_reply("أحتاج مساعدة في البحث عن وظيفة", None)
    assert isinstance(reply, str)
    assert len(reply.strip()) > 0
    assert any("\u0600" <= ch <= "\u06ff" for ch in reply)


def test_cv_intent_fallback_is_job_focused(monkeypatch):
    _force_fallback(monkeypatch)
    reply = _chatbot_reply("Give me CV tips", None)
    assert isinstance(reply, str)
    assert len(reply.strip()) > 0
    assert any(token in reply.lower() for token in ["cv", "skills", "experience", "resume"])
