from sv_mcp.models.result import BaseResult


def test_list_result_defaults_total_to_row_count():
    result = BaseResult(result=[{"id": 1}, {"id": 2}])
    assert result.total == 2
    assert result.has_more is False


def test_explicit_total_and_has_more_are_kept():
    result = BaseResult(result=[{"id": 1}], total=5, has_more=True)
    assert result.total == 5
    assert result.has_more is True


def test_result_without_rows_has_no_total():
    result = BaseResult(error="Not found")
    assert result.total is None
    assert result.has_more is None
