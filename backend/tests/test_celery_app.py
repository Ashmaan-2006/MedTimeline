import importlib
import sys


def test_celery_app_uses_configured_broker_and_serialization() -> None:
    module = importlib.import_module("medgraph_api.core.celery_app")

    celery_app = module.celery_app

    assert celery_app.main == "medgraph_api"
    assert celery_app.conf.broker_url == "amqp://guest:guest@rabbitmq:5672//"
    assert celery_app.conf.result_backend == "rpc://"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.result_expires == 3600
    assert celery_app.conf.task_track_started is True
    assert celery_app.conf.task_acks_late is True


def test_celery_app_import_does_not_import_fastapi_application() -> None:
    sys.modules.pop("medgraph_api.core.celery_app", None)
    sys.modules.pop("medgraph_api.main", None)

    importlib.import_module("medgraph_api.core.celery_app")

    assert "medgraph_api.main" not in sys.modules
