from pipeline.extract import EXPECTED_COLUMNS, validate_source_schema


def test_validate_source_schema_passes_with_valid_columns(mocker):
    """Validate passes when all expected columns are present."""
    mock_engine = mocker.MagicMock()
    mock_inspector = mocker.patch("pipeline.extract.inspect")
    mock_inspector.return_value.get_columns.return_value = [
        {"name": col} for col in EXPECTED_COLUMNS["orders"]
    ]
    # Should not raise
    validate_source_schema(mock_engine, "orders")


def test_validate_source_schema_fails_with_missing_columns(mocker):
    """Validate raises when expected columns are missing."""
    import pytest

    mock_engine = mocker.MagicMock()
    mock_inspector = mocker.patch("pipeline.extract.inspect")
    mock_inspector.return_value.get_columns.return_value = [
        {"name": "order_id"}
    ]
    with pytest.raises(ValueError, match="Missing columns"):
        validate_source_schema(mock_engine, "orders")
