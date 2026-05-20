from pathlib import Path


def test_docker_compose_exposes_runtime_backend_and_worker_services():
    compose = Path("docker-compose.yml").read_text()
    assert "titletrust-worker:" in compose
    assert "titletrust-backend:" in compose
    assert 'OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318/v1/traces' in compose


def test_worker_manifest_uses_existing_healthcheck_entrypoint():
    manifest = Path("k8s/base/worker-deployment.yaml").read_text()
    assert 'python", "-m", "backend.workers.run_worker", "--healthcheck"' in manifest


def test_k8s_has_autoscaling_manifests_for_backend_and_worker():
    assert Path("k8s/base/backend-hpa.yaml").exists()
    assert Path("k8s/base/worker-hpa.yaml").exists()
