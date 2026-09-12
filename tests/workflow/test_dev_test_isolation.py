from pathlib import Path
import re
import tomllib


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SERVICES = ("auth", "event", "media", "analytics")


def test_dev_test_uses_disposable_service_isolated_python_containers():
    script = (REPOSITORY_ROOT / "scripts/dev.ps1").read_text(encoding="utf-8")

    assert "Invoke-Checked python -m alembic" not in script
    assert "Invoke-Checked python -m pytest" not in script
    assert "Invoke-Checked docker run" not in script
    assert "Invoke-Checked docker build" not in script
    assert script.count("Invoke-Checked -FilePath docker -Arguments @(") == 14
    assert script.count('"-w", "/repo"') == 8
    assert "--network host" not in script
    assert '$testNetwork = "$(Get-ComposeProjectName)_default"' in script
    assert "@postgres-test:5432/pawprints_test" in script
    assert "redis://redis-test:6379/0" in script
    assert script.count('"EVENT_DATABASE_URL=$env:EVENT_DATABASE_URL"') == 3
    assert script.count('"ANALYTICS_DATABASE_URL=$env:ANALYTICS_DATABASE_URL"') == 2
    assert script.count('"REDIS_URL=$env:REDIS_URL"') == 1

    for service in PYTHON_SERVICES:
        image = f"pawprints-{service}-test"
        assert f'"build", "--target", "test", "-t", "{image}"' in script
        assert f'"--entrypoint", "python", "{image}"' in script


def test_each_service_dockerfile_has_a_dependency_complete_test_stage():
    for service in PYTHON_SERVICES:
        dockerfile = (REPOSITORY_ROOT / f"services/{service}/Dockerfile").read_text(encoding="utf-8")
        assert " AS test" in dockerfile
        assert f'"services/{service}[dev]"' in dockerfile
        assert "FROM base AS runtime" in dockerfile
        assert f"WORKDIR /repo/services/{service}" in dockerfile
        assert 'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]' in dockerfile

    media_config = tomllib.loads(
        (REPOSITORY_ROOT / "services/media/pyproject.toml").read_text(encoding="utf-8")
    )
    assert any(
        dependency.lower().split("[", 1)[0] == "pillow"
        for dependency in media_config["project"]["dependencies"]
    )


def test_compose_does_not_define_permanent_backend_test_runners():
    compose = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert re.search(r"(?m)^  (auth|event|media|analytics)-test:\s*$", compose) is None


def test_frontend_dependencies_are_installed_only_when_frontend_tests_exist():
    script = (REPOSITORY_ROOT / "scripts/dev.ps1").read_text(encoding="utf-8")

    assert 'Get-ChildItem "apps/web/src" -Recurse -File -Include "*.test.*","*.spec.*"' in script
    assert "if ($frontendTests.Count -gt 0)" in script
    assert "Invoke-Checked npm" not in script
    assert script.count('"node:22-alpine"') == 2
    assert script.count('"-w", "/repo/apps/web"') == 2
    assert re.search(
        r'Invoke-Checked -FilePath docker -Arguments @\(\s*'
        r'"run", "--rm", "--mount", \$repoMount, "-w", "/repo/apps/web",\s*'
        r'"node:22-alpine", "npm", "ci"\s*\)',
        script,
    )
    assert re.search(
        r'Invoke-Checked -FilePath docker -Arguments @\(\s*'
        r'"run", "--rm", "--mount", \$repoMount, "-w", "/repo/apps/web",\s*'
        r'"node:22-alpine", "npm", "test", "--", "--run", "--maxWorkers=2"\s*\)',
        script,
    )
