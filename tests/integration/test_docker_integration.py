"""Integration tests for Docker containerization."""
import pytest
import subprocess
import os


class TestDockerIntegration:
    """Test cases for Docker deployment."""
    
    def test_dockerfile_exists(self):
        """Verify Dockerfile exists."""
        assert os.path.exists("Dockerfile")
    
    def test_docker_compose_exists(self):
        """Verify docker-compose.yml exists."""
        assert os.path.exists("docker-compose.yml")
    
    def test_dockerignore_exists(self):
        """Verify .dockerignore exists."""
        assert os.path.exists(".dockerignore")
    
    def test_docker_compose_config(self):
        """Test docker-compose configuration is valid."""
        result = subprocess.run(
            ["docker-compose", "config"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Docker compose config invalid: {result.stderr}"
    
    def test_dockerfile_content(self):
        """Verify Dockerfile has required content."""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        assert "FROM python:3.11-slim" in content
        assert "WORKDIR /app" in content
        assert "EXPOSE" in content
        assert "PYTHONPATH" in content
    
    def test_docker_compose_services(self):
        """Verify docker-compose has required services."""
        result = subprocess.run(
            ["docker-compose", "config"],
            capture_output=True,
            text=True
        )
        config_output = result.stdout
        
        assert "broker" in config_output
        assert "fmp-lccc" in config_output or "fmp-lfff" in config_output
        assert "sim-manager" in config_output or "sim_manager" in config_output
    
    def test_dockerignore_content(self):
        """Verify .dockerignore excludes unnecessary files."""
        with open(".dockerignore", "r") as f:
            content = f.read()
        
        assert "__pycache__" in content
        assert ".venv" in content or "venv" in content
        assert ".git" in content
        assert ".coverage" in content
    
    @pytest.mark.slow
    def test_docker_build(self):
        """Test Docker image builds successfully. (Slow test)"""
        result = subprocess.run(
            ["docker", "build", "-t", "ddfn-v2-test", "."],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Docker build failed: {result.stderr}"
