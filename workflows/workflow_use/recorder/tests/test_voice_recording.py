import pytest
from unittest.mock import Mock, patch
from workflow_use.recorder.service import record_voice_prompt, get_voice_and_text_prompt, combine_prompts


def test_combine_prompts():
    """Test that combine_prompts correctly combines voice and text inputs."""
    # Test with both inputs
    result = combine_prompts("Voice description", "Text instructions")
    assert "Voice description: Voice description" in result
    assert "Additional instructions: Text instructions" in result
    
    # Test with only voice
    result = combine_prompts("Voice only", "")
    assert "Voice description: Voice only" in result
    assert "Additional instructions" not in result
    
    # Test with only text
    result = combine_prompts("", "Text only")
    assert "Additional instructions: Text only" in result
    assert "Voice description" not in result
    
    # Test with empty inputs
    result = combine_prompts("", "")
    assert result == "Create a workflow based on the provided recording."


@patch('workflow_use.recorder.service.sr.Recognizer')
@patch('workflow_use.recorder.service.whisper.load_model')
def test_record_voice_prompt_success(mock_whisper_model, mock_recognizer):
    """Test successful voice recording and transcription."""
    # Mock the audio recording
    mock_audio = Mock()
    mock_audio.get_wav_data.return_value = b"fake_audio_data"
    
    mock_recognizer_instance = Mock()
    mock_recognizer_instance.listen.return_value = mock_audio
    mock_recognizer.return_value = mock_recognizer_instance
    
    # Mock Whisper transcription
    mock_model = Mock()
    mock_model.transcribe.return_value = {"text": "Hello world"}
    mock_whisper_model.return_value = mock_model
    
    # Mock file operations
    with patch('tempfile.NamedTemporaryFile') as mock_temp_file:
        mock_temp_file.return_value.__enter__.return_value.name = "/tmp/test.wav"
        mock_temp_file.return_value.__enter__.return_value.write = Mock()
        
        with patch('os.unlink'):
            result = record_voice_prompt(duration=5)
    
    assert result == "Hello world"


@patch('workflow_use.recorder.service.sr.Recognizer')
def test_record_voice_prompt_failure(mock_recognizer):
    """Test voice recording failure handling."""
    mock_recognizer_instance = Mock()
    mock_recognizer_instance.listen.side_effect = Exception("Microphone not available")
    mock_recognizer.return_value = mock_recognizer_instance
    
    result = record_voice_prompt(duration=5)
    assert result is None


@patch('workflow_use.recorder.service.record_voice_prompt')
@patch('builtins.input')
def test_get_voice_and_text_prompt(mock_input, mock_record_voice):
    """Test getting both voice and text prompts."""
    mock_record_voice.return_value = "Voice transcription"
    mock_input.return_value = "Text prompt"
    
    voice_text, text_prompt = get_voice_and_text_prompt()
    
    assert voice_text == "Voice transcription"
    assert text_prompt == "Text prompt"


if __name__ == "__main__":
    pytest.main([__file__]) 