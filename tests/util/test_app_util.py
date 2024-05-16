from narrative_llm_agent.util.app import (
    get_processed_app_spec_params,
    process_param_type,
    get_ws_object_refs,
    is_valid_ref,
    is_valid_upa,
    generate_input,
    resolve_ref,
    resolve_ref_if_typed,
    resolve_single_ref,
    system_variable,
    transform_param_value
)
from narrative_llm_agent.kbase.service_client import ServerError

from tests.test_data.test_data import load_test_data_json
from pathlib import Path
import pytest

MOCK_WS_ID = 1000
MOCK_WS_NAME = "test_workspace"

@pytest.fixture(scope="module")
def app_spec():
    """
    Loads an app spec for testing. This is the NarrativeTest/test_input_params app spec.
    """
    app_spec_path = Path("app_spec_data") / "test_app_spec.json"
    spec = load_test_data_json(app_spec_path)
    return spec

@pytest.fixture(scope="module")
def expected_app_params():
    """
    Loads the pre-processed app spec params from the NarrativeTest/test_input_params spec.
    """
    expected_params_path = Path("app_spec_data") / "app_spec_processed_params.json"
    params_spec = load_test_data_json(expected_params_path)
    return params_spec

@pytest.fixture(scope="module")
def input_params():
    """
    Loads a sample filled out parameter set using the NarrativeTest/test_input_params app.
    """
    params_path = Path("app_spec_data") / "test_app_spec_inputs.json"
    params = load_test_data_json(params_path)
    return params

def test_get_spec_params(app_spec: dict, expected_app_params: dict):
    params = get_processed_app_spec_params(app_spec)
    assert params
    assert params == expected_app_params

@pytest.mark.parametrize("test_type", ["foo", "text", "textarea", "other"])
def test_process_param_type_simple(test_type: str):
    param = {
        "field_type": test_type,
    }
    assert process_param_type(param) == (test_type, [])

@pytest.mark.parametrize("number_type", ["int", "float"])
def test_process_param_type_number(number_type: str):
    param = {
        "field_type": "text",
        "text_options": {
            "validate_as": number_type,
            f"max_{number_type}": 100,
            f"min_{number_type}": 0
        }
    }
    assert process_param_type(param) == (number_type, [0, 100])

def test_process_param_type_data_object():
    ws_types = ["KBaseGenomes.Genome", "SomeOther.Genome"]
    param = {
        "field_type": "text",
        "text_options": {
            "valid_ws_types": ws_types
        }
    }
    assert process_param_type(param) == ("data_object", ws_types)

def test_process_param_type_dropdown():
    dropdown_opts = [{
        "value": "foo",
        "display": "Foo"
    }, {
        "value": "bar",
        "display": "Bar"
    }]
    param = {
        "field_type": "dropdown",
        "dropdown_options": {
            "options": dropdown_opts
        }
    }
    assert process_param_type(param) == ("dropdown", ["Foo", "Bar"])

def test_get_ws_object_refs(app_spec: dict, input_params: dict):
    expected_refs = set(["1/2/3", "1/3/1", "1/4/1"])
    assert set(get_ws_object_refs(app_spec, input_params)) == expected_refs

valid_upas = ["1/2/3", "11/22/33"]
invalid_upas = ["1/2", "1/2/3/4", None, 1, "nope"]
@pytest.mark.parametrize(
    "test_str,expected",
    [(good, True) for good in valid_upas] +
    [(bad, False) for bad in invalid_upas]
)
def test_is_valid_upa(test_str: str, expected: bool):
    assert is_valid_upa(test_str) == expected

valid_refs = valid_upas + ["some/ref", "1/2"]
invalid_refs = invalid_upas[1:]
@pytest.mark.parametrize(
    "test_str,expected",
    [(good, True) for good in valid_refs] +
    [(bad, False) for bad in invalid_refs]
)
def test_is_valid_ref(test_str: str, expected: bool):
    assert is_valid_ref(test_str) == expected

def test_generate_input():
    prefix = "pre"
    suffix = "suf"
    num_symbols = 8
    generator = {"symbols": num_symbols, "prefix": prefix, "suffix": suffix}
    rand_str = generate_input(generator)
    assert rand_str.startswith(prefix)
    assert rand_str.endswith(suffix)
    assert len(rand_str) == len(prefix) + len(suffix) + num_symbols

def test_generate_input_default():
    rand_str = generate_input()
    assert len(rand_str) == 8

def test_generate_input_bad():
    with pytest.raises(ValueError):
        generate_input({"symbols": "foo"})
    with pytest.raises(ValueError):
        generate_input({"symbols": -1})

def test_resolve_ref(mock_workspace):
    upa = "1000/2/3"
    assert resolve_ref(upa, MOCK_WS_ID, mock_workspace) == upa

def test_resolve_ref_list(mock_workspace):
    ref_list = ["1000/2", "1000/bar"]
    assert resolve_ref(ref_list, MOCK_WS_ID, mock_workspace) == ["1000/2/3", "1000/3/4"]

@pytest.mark.parametrize("ref", [("1/fdsa/3"), (["1000/2", "1/asdf/3"])])
def test_resolve_ref_fail(ref, mock_workspace):
    with pytest.raises(ServerError):
        resolve_ref(ref, MOCK_WS_ID, mock_workspace)

typed_single_cases = [
    (True, "data_object", "foo"),
    (False, "data_object", "1000/2/3"),
    (True, "text", "foo"),
    (False, "text", "foo"),
]
@pytest.mark.parametrize("is_output,param_type,expected", typed_single_cases)
def test_resolve_ref_if_typed_single(is_output, param_type, expected, mock_workspace):
    spec_param = {
        "is_output_object": is_output,
        "type": param_type
    }
    assert resolve_ref_if_typed("foo", spec_param, MOCK_WS_ID, mock_workspace) == expected

typed_list_cases = [
    (True, "data_object", ["foo", "bar"]),
    (False, "data_object", ["1000/2/3", "1000/3/4"]),
    (True, "text", ["foo", "bar"]),
    (False, "text", ["foo", "bar"]),
]
@pytest.mark.parametrize("is_output,param_type,expected", typed_list_cases)
def test_resolve_ref_if_typed_single(is_output, param_type, expected, mock_workspace):
    spec_param = {
        "is_output_object": is_output,
        "type": param_type
    }
    assert resolve_ref_if_typed(["foo", "bar"], spec_param, MOCK_WS_ID, mock_workspace) == expected

single_ref_cases = [
    ("1000/2"),
    ("1000/2/3"),
    ("1000/foo"),
    ("1000/foo/3")
]
@pytest.mark.parametrize("value", single_ref_cases)
def test_resolve_single_ref(value, mock_workspace):
    assert resolve_single_ref(value, MOCK_WS_ID, mock_workspace) == "1000/2/3"

def test_resolve_single_ref_fail(mock_workspace):
    with pytest.raises(ValueError, match="has too many slashes"):
        resolve_single_ref("not/a/real/upa", MOCK_WS_ID, mock_workspace)

def test_resolve_single_ref_not_found(mock_workspace):
    with pytest.raises(ServerError):
        resolve_single_ref("not_found", MOCK_WS_ID, mock_workspace)

@pytest.mark.parametrize("input,expected", [
    ("workspace", MOCK_WS_NAME),
    ("workspace_id", MOCK_WS_ID),
    ("user_id", None),
    ("not_a_sys_var", None)
])
def test_system_variable(input, expected, mock_workspace):
    assert(system_variable(input, MOCK_WS_ID, mock_workspace)) == expected


##### COPIED FROM kbase/narrative repo #####
# transform_param_value tests
transform_param_value_simple_cases = [
    ("string", None, None, None),
    ("string", "foo", None, "foo"),
    ("string", 123, None, "123"),
    ("string", ["a", "b", "c"], None, "a,b,c"),
    ("string", {"a": "b", "c": "d"}, None, "a=b,c=d"),
    ("string", [], None, ""),
    ("string", {}, None, ""),
    ("int", "1", None, 1),
    ("int", None, None, None),
    ("int", "", None, None),
    ("list<string>", [1, 2, 3], None, ["1", "2", "3"]),
    ("list<int>", ["1", "2", "3"], None, [1, 2, 3]),
    ("list<string>", "asdf", None, ["asdf"]),
    ("list<int>", "1", None, [1]),
]


@pytest.mark.parametrize(
    ("transform_type", "value", "spec_param", "expected"),
    transform_param_value_simple_cases,
)
def test_transform_param_value_simple(transform_type, value, spec_param, expected, mock_workspace):
    assert transform_param_value(transform_type, value, spec_param, MOCK_WS_ID, mock_workspace) == expected


def test_transform_param_value_fail(mock_workspace):
    ttype = "foobar"
    with pytest.raises(ValueError, match=f"Unsupported Transformation type: {ttype}"):
        transform_param_value(ttype, "foo", None, MOCK_WS_ID, mock_workspace)


textsubdata_cases = [
    (None, None),
    ("asdf", "asdf"),
    (123, "123"),
    (["1", "2", "3"], "1,2,3"),
    ({"a": "b", "c": "d"}, "a=b,c=d"),
]


@pytest.mark.parametrize(("value", "expected"), textsubdata_cases)
def test_transform_param_value_textsubdata(value, expected, mock_workspace):
    spec = {"type": "textsubdata"}
    assert transform_param_value(None, value, spec, MOCK_WS_ID, mock_workspace) == expected
