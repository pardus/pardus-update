import pytest
import os
import tempfile
from src.Utils import Utils

@pytest.fixture
def utils_instance():
    return Utils()

def test_get_path_size_nonexistent(utils_instance, capsys):
    path = "/tmp/nonexistent_path_for_test"
    assert utils_instance.get_path_size(path) == 0
    captured = capsys.readouterr()
    assert f"{path} is not readable." in captured.out

def test_get_path_size_empty_dir(utils_instance):
    with tempfile.TemporaryDirectory() as tmpdir:
        assert utils_instance.get_path_size(tmpdir) == 0

def test_get_path_size_with_file(utils_instance):
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "test_file.txt")
        with open(file_path, "w") as f:
            f.write("hello")
        assert utils_instance.get_path_size(tmpdir) == 5 # "hello" is 5 bytes
        os.remove(file_path) # clean up the file manually

def test_get_session_type(utils_instance, monkeypatch):
    # Test with XDG_SESSION_TYPE set
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    assert utils_instance.get_session_type() == "X11"

    # Test with XDG_SESSION_TYPE not set (should return "None" capitalized)
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    assert utils_instance.get_session_type() == "None"

def test_get_desktop_env(utils_instance, monkeypatch):
    # Test with XDG_CURRENT_DESKTOP set
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "XFCE")
    assert utils_instance.get_desktop_env() == "XFCE"

    # Test with XDG_CURRENT_DESKTOP not set
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    assert utils_instance.get_desktop_env() == "None"
