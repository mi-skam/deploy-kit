"""E2E tests for hash-based tarball transfer optimization."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from deploy_kit import docker
from deploy_kit.backends import compose


@pytest.fixture
def temp_dist(tmp_path, monkeypatch):
    """Create a temporary dist directory and change to tmp_path."""
    monkeypatch.chdir(tmp_path)
    dist = tmp_path / "dist"
    dist.mkdir()
    return dist


@pytest.fixture
def mock_config():
    """Create a mock DeployConfig."""
    config = MagicMock()
    config.project_name = "test-project"
    config.image_tag = "abc1234"
    config.port = 8000
    config.healthcheck_path = "/"
    config.keep_tarballs = 3
    return config


class TestComputeFileHash:
    """Tests for compute_file_hash function."""

    def test_computes_sha256_hash(self, tmp_path):
        """Should compute correct SHA256 hash of file content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        result = docker.compute_file_hash(test_file)

        # SHA256 of "hello world" (without newline)
        assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert len(result) == 64

    def test_handles_binary_files(self, tmp_path):
        """Should handle binary file content."""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"\x00\x01\x02\x03")

        result = docker.compute_file_hash(test_file)

        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_different_content_different_hash(self, tmp_path):
        """Different file contents should produce different hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        hash1 = docker.compute_file_hash(file1)
        hash2 = docker.compute_file_hash(file2)

        assert hash1 != hash2


class TestSaveImageCreatesHashFile:
    """Tests for hash file creation during image save."""

    @patch("deploy_kit.docker.docker")
    def test_creates_hash_file_after_save(self, mock_docker, temp_dist, mock_config):
        """Should create .sha256 file alongside tarball."""

        def fake_save(image_tag, output):
            output.write_bytes(b"fake docker image content")

        mock_docker.image.save.side_effect = fake_save

        tarball = docker.save_image(mock_config)

        hash_file = tarball.parent / f"{tarball.name}.sha256"
        assert hash_file.exists()

        content = hash_file.read_text()
        assert tarball.name in content
        # Format: "<hash>  <filename>\n"
        parts = content.strip().split("  ")
        assert len(parts) == 2
        assert len(parts[0]) == 64  # SHA256 hex length

    @patch("deploy_kit.docker.docker")
    def test_hash_matches_tarball_content(self, mock_docker, temp_dist, mock_config):
        """Hash in file should match actual tarball hash."""

        def fake_save(image_tag, output):
            output.write_bytes(b"fake docker image content")

        mock_docker.image.save.side_effect = fake_save

        tarball = docker.save_image(mock_config)

        hash_file = tarball.parent / f"{tarball.name}.sha256"
        stored_hash = hash_file.read_text().strip().split("  ")[0]
        computed_hash = docker.compute_file_hash(tarball)

        assert stored_hash == computed_hash


class TestHashComparison:
    """Tests for hash comparison logic in compose deploy."""

    def test_sha256_pattern_validation(self):
        """SHA256_PATTERN should validate correct hash format."""
        valid_hash = "a" * 64
        invalid_short = "a" * 63
        invalid_chars = "g" * 64
        invalid_uppercase = "A" * 64

        assert compose.SHA256_PATTERN.match(valid_hash)
        assert not compose.SHA256_PATTERN.match(invalid_short)
        assert not compose.SHA256_PATTERN.match(invalid_chars)
        assert not compose.SHA256_PATTERN.match(invalid_uppercase)


class TestTransferSkipLogic:
    """E2E tests for the transfer skip logic."""

    @patch("deploy_kit.backends.compose.run_script")
    @patch("deploy_kit.backends.compose.run_script_capture")
    @patch("deploy_kit.backends.compose.find_compose_template")
    @patch("deploy_kit.docker.docker")
    def test_skips_transfer_when_hashes_match(
        self,
        mock_docker,
        mock_find_template,
        mock_run_capture,
        mock_run_script,
        temp_dist,
        mock_config,
    ):
        """Should skip tarball transfer when remote hash matches local."""
        # Setup: create tarball
        def fake_save(image_tag, output):
            output.write_bytes(b"fake docker image content")

        mock_docker.image.save.side_effect = fake_save
        mock_find_template.return_value = Path("docker-compose.prod.yml.template")

        # First, save to get the actual hash
        tarball = docker.save_image(mock_config)
        local_hash = docker.compute_file_hash(tarball)

        # Mock remote returning the same hash
        mock_run_capture.return_value = local_hash

        # Run deploy
        compose.deploy("user@host", mock_config, None)

        # Verify ssh_transfer.sh was called with skip_tarball="true"
        transfer_call = [c for c in mock_run_script.call_args_list if "ssh_transfer.sh" in str(c)]
        assert len(transfer_call) == 1
        args = transfer_call[0][0][1]  # Second positional arg is the args list
        assert args[-1] == "true"  # Last arg is skip_tarball

    @patch("deploy_kit.backends.compose.run_script")
    @patch("deploy_kit.backends.compose.run_script_capture")
    @patch("deploy_kit.backends.compose.find_compose_template")
    @patch("deploy_kit.docker.docker")
    def test_transfers_when_hashes_differ(
        self,
        mock_docker,
        mock_find_template,
        mock_run_capture,
        mock_run_script,
        temp_dist,
        mock_config,
    ):
        """Should transfer tarball when remote hash differs from local."""

        def fake_save(image_tag, output):
            output.write_bytes(b"fake docker image content")

        mock_docker.image.save.side_effect = fake_save
        mock_find_template.return_value = Path("docker-compose.prod.yml.template")

        # Mock remote returning a different hash
        mock_run_capture.return_value = "b" * 64

        compose.deploy("user@host", mock_config, None)

        # Verify ssh_transfer.sh was called with skip_tarball="false"
        transfer_call = [c for c in mock_run_script.call_args_list if "ssh_transfer.sh" in str(c)]
        assert len(transfer_call) == 1
        args = transfer_call[0][0][1]
        assert args[-1] == "false"

    @patch("deploy_kit.backends.compose.run_script")
    @patch("deploy_kit.backends.compose.run_script_capture")
    @patch("deploy_kit.backends.compose.find_compose_template")
    @patch("deploy_kit.docker.docker")
    def test_transfers_when_remote_file_missing(
        self,
        mock_docker,
        mock_find_template,
        mock_run_capture,
        mock_run_script,
        temp_dist,
        mock_config,
    ):
        """Should transfer tarball when remote file doesn't exist."""

        def fake_save(image_tag, output):
            output.write_bytes(b"fake docker image content")

        mock_docker.image.save.side_effect = fake_save
        mock_find_template.return_value = Path("docker-compose.prod.yml.template")

        # Mock remote returning empty string (file doesn't exist)
        mock_run_capture.return_value = ""

        compose.deploy("user@host", mock_config, None)

        transfer_call = [c for c in mock_run_script.call_args_list if "ssh_transfer.sh" in str(c)]
        assert len(transfer_call) == 1
        args = transfer_call[0][0][1]
        assert args[-1] == "false"

    @patch("deploy_kit.backends.compose.run_script")
    @patch("deploy_kit.backends.compose.run_script_capture")
    @patch("deploy_kit.backends.compose.find_compose_template")
    @patch("deploy_kit.docker.docker")
    def test_transfers_when_ssh_fails(
        self,
        mock_docker,
        mock_find_template,
        mock_run_capture,
        mock_run_script,
        temp_dist,
        mock_config,
    ):
        """Should transfer tarball when SSH hash check fails."""

        def fake_save(image_tag, output):
            output.write_bytes(b"fake docker image content")

        mock_docker.image.save.side_effect = fake_save
        mock_find_template.return_value = Path("docker-compose.prod.yml.template")

        # Mock SSH command failure
        mock_run_capture.side_effect = subprocess.CalledProcessError(1, "ssh")

        compose.deploy("user@host", mock_config, None)

        transfer_call = [c for c in mock_run_script.call_args_list if "ssh_transfer.sh" in str(c)]
        assert len(transfer_call) == 1
        args = transfer_call[0][0][1]
        assert args[-1] == "false"

    @patch("deploy_kit.backends.compose.run_script")
    @patch("deploy_kit.backends.compose.run_script_capture")
    @patch("deploy_kit.backends.compose.find_compose_template")
    @patch("deploy_kit.docker.docker")
    def test_transfers_when_remote_returns_invalid_hash(
        self,
        mock_docker,
        mock_find_template,
        mock_run_capture,
        mock_run_script,
        temp_dist,
        mock_config,
    ):
        """Should transfer tarball when remote returns invalid hash format."""

        def fake_save(image_tag, output):
            output.write_bytes(b"fake docker image content")

        mock_docker.image.save.side_effect = fake_save
        mock_find_template.return_value = Path("docker-compose.prod.yml.template")

        # Mock remote returning invalid hash (too short)
        mock_run_capture.return_value = "abc123"

        compose.deploy("user@host", mock_config, None)

        transfer_call = [c for c in mock_run_script.call_args_list if "ssh_transfer.sh" in str(c)]
        assert len(transfer_call) == 1
        args = transfer_call[0][0][1]
        assert args[-1] == "false"


class TestCleanupWithHashFiles:
    """Tests for cleanup of hash files alongside tarballs."""

    def test_cleanup_removes_hash_files(self, temp_dist):
        """cleanup_old_tarballs should also remove corresponding hash files."""
        # Create tarballs and hash files
        for i in range(5):
            tarball = temp_dist / f"test-project-tag{i}.tar.gz"
            hash_file = temp_dist / f"test-project-tag{i}.tar.gz.sha256"
            tarball.write_bytes(b"content")
            hash_file.write_text(f"{'a'*64}  {tarball.name}\n")

        docker.cleanup_old_tarballs("test-project", keep=2)

        remaining_tarballs = list(temp_dist.glob("*.tar.gz"))
        remaining_hashes = list(temp_dist.glob("*.sha256"))

        # Should keep 2 tarballs and their hash files
        assert len([f for f in remaining_tarballs if not f.name.endswith(".sha256")]) == 2
        assert len(remaining_hashes) == 2
