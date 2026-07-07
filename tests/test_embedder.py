"""QwenEmbedder 测试"""
import pytest
from unittest.mock import MagicMock

from agents.retrieval.embedder import QwenEmbedder


def test_embed_empty_list():
    embedder = QwenEmbedder(api_key="test-key")
    result = embedder.embed([])
    assert result == []


def test_embed_single_mocked():
    embedder = QwenEmbedder(api_key="test-key")
    mock_embedding = MagicMock()
    mock_embedding.embedding = [0.1] * 1024
    mock_response = MagicMock()
    mock_response.data = [mock_embedding]
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = mock_response

    embedder._client = mock_client
    result = embedder.embed(["测试文本"])
    assert len(result) == 1
    assert len(result[0]) == 1024
    mock_client.embeddings.create.assert_called_once()


def test_embed_single_convenience():
    embedder = QwenEmbedder(api_key="test-key")
    mock_embedding = MagicMock()
    mock_embedding.embedding = [0.2] * 1024
    mock_response = MagicMock()
    mock_response.data = [mock_embedding]
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = mock_response

    embedder._client = mock_client
    result = embedder.embed_single("单条文本")
    assert len(result) == 1024
