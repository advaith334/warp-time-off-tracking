from app.main import health


class _Result:
    @staticmethod
    def scalar() -> int:
        return 1


class _Session:
    @staticmethod
    def execute(_query) -> _Result:
        return _Result()


def test_health_reports_the_database_is_up():
    assert health(_Session()) == {"status": "ok", "database": "up"}
