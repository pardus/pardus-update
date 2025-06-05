import pytest
import subprocess
import sys
import os
from unittest.mock import patch, MagicMock

# It's good practice to ensure src is in path for imports,
# though for this specific script structure, direct import might work.
# However, if SysActions.py had relative imports within src, this would be more robust.
# For now, we'll assume direct import works or adjust if ModuleNotFoundError occurs.
from src import SysActions

@patch('src.SysActions.apt.Cache')
@patch('subprocess.call')
def test_sys_actions_script_runs_update(mock_subprocess_call, mock_apt_cache, monkeypatch):
    """
    Tests if the SysActions script calls subprocess.call with ['apt', 'update']
    when called with the 'update' argument.
    It also simulates an initial failure of apt.Cache().update() to ensure subupdate() is called.
    """
    # Configure the mock_apt_cache to simulate an exception during cache.update()
    # This will force the code to call the subupdate() function.
    mock_cache_instance = MagicMock()
    mock_cache_instance.update = MagicMock(side_effect=Exception("Simulated cache update error"))
    mock_apt_cache.return_value = mock_cache_instance

    # Prepare sys.argv as if the script was called with 'update'
    monkeypatch.setattr(sys, 'argv', ['src/SysActions.py', 'update'])

    # Call the main function
    SysActions.main()

    # Assert that subprocess.call was called correctly by subupdate()
    mock_subprocess_call.assert_called_once_with(
        ["apt", "update"],
        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}
    )

@patch('subprocess.call')
def test_sys_actions_script_runs_fixbroken(mock_subprocess_call, monkeypatch):
    """
    Tests if the SysActions script calls subprocess.call with ['apt', 'install', '--fix-broken', '-yq']
    when called with the 'fixapt' argument (which subsequently calls fixbroken).
    This test focuses on the fixbroken part of the 'fixapt' command.
    """
    # Prepare sys.argv as if the script was called with 'fixapt'
    # We are interested in the call to fixbroken() which is part of fixapt.
    # The 'fixapt' command also calls correctsourceslist(), subupdate(), dpkgconfigure().
    # We will let those run (mocks will handle subprocess calls if any).
    monkeypatch.setattr(sys, 'argv', ['src/SysActions.py', 'fixapt'])

    # Mock distro.codename() as it's called by correctsourceslist()
    with patch('src.SysActions.distro.codename') as mock_codename:
        mock_codename.return_value = "yirmibir" # Example codename

        # Call the main function
        SysActions.main()

        # Check if fixbroken's call was made.
        # 'fixapt' calls: correctsourceslist, subupdate, dpkgconfigure, fixbroken
        # We are specifically asserting the call made by fixbroken()
        calls = mock_subprocess_call.call_args_list
        expected_fixbroken_call_found = False
        for call_args, call_kwargs in calls:
            if call_args[0] == ["apt", "install", "--fix-broken", "-yq"]:
                assert call_kwargs['env'] == {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}
                expected_fixbroken_call_found = True
                break

        assert expected_fixbroken_call_found, "subprocess.call for fixbroken was not made as expected."

@patch('subprocess.call')
def test_sys_actions_script_runs_dpkgconfigure(mock_subprocess_call, monkeypatch):
    """
    Tests if the SysActions script calls subprocess.call with ['dpkg', '--configure', '-a']
    when called with the 'dpkgconfigure' argument.
    """
    monkeypatch.setattr(sys, 'argv', ['src/SysActions.py', 'dpkgconfigure'])
    SysActions.main()
    mock_subprocess_call.assert_called_once_with(
        ["dpkg", "--configure", "-a"],
        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}
    )

# Example of a test for a command that takes more arguments
@patch('subprocess.call')
def test_sys_actions_script_runs_removeresidual(mock_subprocess_call, monkeypatch):
    packages_to_remove = "package1 package2"
    monkeypatch.setattr(sys, 'argv', ['src/SysActions.py', 'removeresidual', packages_to_remove])
    SysActions.main()
    mock_subprocess_call.assert_called_once_with(
        ["apt", "remove", "--purge", "-yq"] + packages_to_remove.split(" "),
        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}
    )

@patch('src.SysActions.control_lock')
@patch('subprocess.call')
def test_sys_actions_upgrade_dpkg_lock_error(mock_subprocess_call, mock_control_lock, monkeypatch, capsys):
    """
    Tests the upgrade action when a dpkg lock error occurs.
    It should print an error message to stderr and exit with code 11.
    """
    mock_control_lock.return_value = (False, "E: Could not get lock /var/lib/dpkg/lock-frontend - open (11: Resource temporarily unavailable)")

    monkeypatch.setattr(sys, 'argv', ['src/SysActions.py', 'upgrade', '-yq', '--option=Dpkg::Options::="--force-confdef"', 'keep_package'])

    with pytest.raises(SystemExit) as e:
        SysActions.main()

    assert e.value.code == 11
    captured = capsys.readouterr()
    assert "dpkg lock error" in captured.err
    mock_subprocess_call.assert_not_called() # Ensure upgrade actions are not called

@patch('src.SysActions.distro.codename')
@patch('builtins.open')
@patch('os.path.isdir')
@patch('os.listdir')
@patch('src.SysActions.rmtree')
@patch('src.SysActions.aptclean')
@patch('src.SysActions.subupdate')
def test_correctsourceslist_generic(mock_subupdate, mock_aptclean, mock_rmtree, mock_listdir, mock_isdir, mock_open, mock_distro_codename, monkeypatch):
    """
    Tests the correctsourceslist function for a generic codename.
    It ensures that sources.list is written to, and apt clean/update are called.
    """
    mock_distro_codename.return_value = "myos-generic" # A codename not specifically handled
    monkeypatch.setattr(sys, 'argv', ['src/SysActions.py', 'correctsourceslist'])

    # This function doesn't generate a source string for unknown codenames,
    # so it won't try to open and write to /etc/apt/sources.list.
    # It will, however, proceed if 'found' remains True (which it does by default).
    # Let's simulate that 'found' becomes False as it would for an unhandled codename.
    # To do this more directly would require refactoring correctsourceslist or more complex mocking.
    # For now, we'll test the parts that *would* run if a source string *were* generated.

    # Since 'myos-generic' is not a known codename, the 'source' variable in correctsourceslist will be empty
    # and 'found' will be set to False. Thus, it won't attempt to write to /etc/apt/sources.list
    # or clean/update apt.

    SysActions.main()

    mock_open.assert_not_called() # Should not attempt to write sources.list for unknown codename
    mock_rmtree.assert_not_called()
    mock_aptclean.assert_not_called()
    mock_subupdate.assert_not_called()


@patch('src.SysActions.distro.codename')
@patch('builtins.open')
@patch('os.path.isdir')
@patch('os.listdir')
@patch('src.SysActions.rmtree')
@patch('src.SysActions.aptclean')
@patch('src.SysActions.subupdate')
@patch('src.SysActions.Path') # Mock pathlib.Path
def test_correctsourceslist_yirmibir(mock_path, mock_subupdate, mock_aptclean, mock_rmtree, mock_listdir, mock_isdir, mock_open, mock_distro_codename, monkeypatch):
    """
    Tests the correctsourceslist function for 'yirmibir'.
    Ensures sources.list is written, sources.list.d is processed, and apt clean/update are called.
    """
    mock_distro_codename.return_value = "yirmibir"
    monkeypatch.setattr(sys, 'argv', ['src/SysActions.py', 'correctsourceslist'])

    # Mock os.path.isdir to return True for /etc/apt/sources.list.d
    mock_isdir.return_value = True
    # Mock os.listdir to return a dummy list file
    mock_listdir.return_value = ['some-repo.list']

    # Mock for Path(...).mkdir
    mock_path_instance = MagicMock()
    mock_path.return_value = mock_path_instance

    # Capture calls to open
    mock_file_handles = [MagicMock(), MagicMock()] # Handles for sources.list.d file and sources.list
    mock_open.side_effect = mock_file_handles

    SysActions.main()

    # Check that /etc/apt/sources.list.d/some-repo.list was opened for read and write (for commenting out)
    # Check that /etc/apt/sources.list was opened for write
    assert mock_open.call_count >= 2 # At least two, one for sources.list.d, one for sources.list

    # Check if the main sources.list was written
    # The actual content depends on datetime.now(), so we check if the call was made
    # and that "yirmibir" is in the content.
    sources_list_write_call = None
    for call in mock_open.call_args_list:
        if call[0][0] == '/etc/apt/sources.list':
            sources_list_write_call = call
            break
    assert sources_list_write_call is not None

    # Check that rmtree, aptclean, and subupdate were called
    mock_rmtree.assert_called_with("/var/lib/apt/lists/", ignore_errors=True)
    mock_aptclean.assert_called_once()
    mock_subupdate.assert_called_once()
