def read_json_file(file_path):
    import json
    with open(file_path, 'r') as file:
        return json.load(file)

def write_json_file(file_path, data):
    import json
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

def validate_json_schema(data, schema):
    from jsonschema import validate, ValidationError
    try:
        validate(instance=data, schema=schema)
        return True
    except ValidationError as e:
        return False

def flatten_list(nested_list):
    return [item for sublist in nested_list for item in sublist]

def generate_unique_id(existing_ids):
    import uuid
    new_id = str(uuid.uuid4())
    while new_id in existing_ids:
        new_id = str(uuid.uuid4())
    return new_id