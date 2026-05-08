"""File manage service - field filtering for export"""


def filter_record_fields(record: dict, fields: list[str]) -> dict:
    """Filter a single record to only include selected fields.

    Selected fields that don't exist in the record are included with empty string "".
    Extra sub-fields that don't exist in the record's extra object are also included as "".

    Args:
        record: The original data record (dict).
        fields: List of selected field names. Top-level fields are plain names
                (e.g. "id", "domain"). Extra sub-fields are prefixed with "extra."
                (e.g. "extra.options", "extra.confidence"). Matching is case-insensitive.

    Returns:
        A new dict with only the selected fields. Missing fields get "".
        If some extra sub-fields are selected, the "extra" (or "extra_fields") key
        keeps only those sub-fields. If no extra sub-fields are selected, extra key is omitted.
    """
    if not fields:
        return record

    # Build case-insensitive lookup: desired lowercase → original field name from selection
    lower_top_level = {f.lower(): f for f in fields if not f.startswith("extra.")}
    lower_extra = {f[len("extra."):].lower(): f[len("extra."):] for f in fields if f.startswith("extra.")}

    # Find the extra key in the record (could be "extra" or "extra_fields")
    extra_key = None
    extra_data = None
    for candidate in ("extra", "extra_fields"):
        if candidate in record and isinstance(record[candidate], dict) and not isinstance(record[candidate], list):
            extra_key = candidate
            extra_data = record[candidate]
            break

    # Build a reverse map: actual record key lowercase → actual record key (preserve casing)
    record_key_map = {k.lower(): k for k in record.keys() if k != extra_key}

    # Top-level fields: always present, "" if missing; output key name follows user selection
    result = {}
    for desired_lower, desired_name in lower_top_level.items():
        if desired_lower in record_key_map:
            result[desired_name] = record[record_key_map[desired_lower]]
        else:
            result[desired_name] = ""

    # Extra sub-fields: always present if any extra sub-field is selected; output key name follows user selection
    if lower_extra:
        # Determine which extra key to use in output
        output_extra_key = extra_key or "extra"
        filtered_extra = {}
        # Build a reverse map for extra sub-keys
        extra_key_map = {}
        if extra_data:
            extra_key_map = {k.lower(): k for k in extra_data.keys()}
        for desired_lower, desired_name in lower_extra.items():
            if desired_lower in extra_key_map:
                filtered_extra[desired_name] = extra_data[extra_key_map[desired_lower]]
            else:
                filtered_extra[desired_name] = ""
        result[output_extra_key] = filtered_extra

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