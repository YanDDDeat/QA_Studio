"""File manage service - field filtering for export"""


def filter_record_fields(record: dict, fields: list[str]) -> dict:
    """Filter a single record to only include selected fields.

    Args:
        record: The original data record (dict).
        fields: List of selected field names. Top-level fields are plain names
                (e.g. "id", "domain"). Extra sub-fields are prefixed with "extra."
                (e.g. "extra.options", "extra.confidence"). Matching is case-insensitive.

    Returns:
        A new dict with only the selected fields. If some extra sub-fields are
        selected, the "extra" (or "extra_fields") key keeps only those sub-fields.
        If no extra sub-fields are selected, the "extra"/"extra_fields" key is removed.
    """
    if not fields:
        return record

    # Build case-insensitive lookup sets
    lower_top_level = {f.lower(): f for f in fields if not f.startswith("extra.")}
    lower_extra = {f[len("extra."):].lower(): f[len("extra."):] for f in fields if f.startswith("extra.")}

    result = {}

    # The extra field may be stored as "extra" or "extra_fields" depending on the pipeline stage
    extra_key = None
    extra_data = None
    for candidate in ("extra", "extra_fields"):
        if candidate in record and isinstance(record[candidate], dict) and not isinstance(record[candidate], list):
            extra_key = candidate
            extra_data = record[candidate]
            break

    # Keep selected top-level fields (case-insensitive match against actual record keys)
    for key, value in record.items():
        if key == extra_key:
            continue  # handle extra separately below
        if key.lower() in lower_top_level:
            # Use the actual record key name (preserve original casing)
            result[key] = value

    # Handle extra sub-fields
    if extra_key and extra_data:
        filtered_extra = {}
        for sub_key, sub_value in extra_data.items():
            if sub_key.lower() in lower_extra:
                # Preserve actual sub-key casing from the data
                filtered_extra[sub_key] = sub_value
        if filtered_extra:
            result[extra_key] = filtered_extra
        # If no extra sub-fields selected, extra key is simply omitted

    return result


def filter_records_fields(records: list, fields: list[str]) -> list:
    """Filter a list of records to only include selected fields.

    Args:
        records: List of data records (each a dict).
        fields: List of selected field names (same format as filter_record_fields).

    Returns:
        List of filtered records.
    """
    return [filter_record_fields(r, fields) for r in records]