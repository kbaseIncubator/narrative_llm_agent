import pytest
from unittest.mock import Mock
from narrative_llm_agent.kbase.service_client import ServiceClient, ServerError
from narrative_llm_agent.kbase.clients.workspace import Workspace, WorkspaceInfo
from .test_data.test_data import get_test_narrative, load_test_data_json
from langchain_core.language_models.llms import LLM
from pathlib import Path

@pytest.fixture
def mock_auth_request(requests_mock):
    def auth_request(url: str, token: str, return_value: dict, status_code: int=200):
        requests_mock.register_uri(
            "GET",
            url,
            request_headers={"Authorization": token},
            json=return_value,
            status_code=status_code
        )
    return auth_request

@pytest.fixture
def mock_auth_request_ok(mock_auth_request):
    def auth_request_ok(url: str, token: str):
        auth_success = {
            "type": "Login",
            "id": "blah_blah_token_id",
            "expires": 1714583567055,
            "created": 1706807567055,
            "name": "llm agency",
            "user": "j_random_user",
            "custom": {},
            "cachefor": 300000
        }
        mock_auth_request(url, token, auth_success)
        return auth_success
    return auth_request_ok

@pytest.fixture
def mock_auth_request_bad_token(mock_auth_request):
    def auth_request_bad_token(url: str, token: str):
        unauth_error = {
            "error": {
                "httpcode": 401,
                "httpstatus": "Unauthorized",
                "appcode": 10020,
                "apperror": "Invalid token",
                "message": "10020 Invalid token",
                "callid": "12345",
                "time": 1708720112853
            }
        }
        mock_auth_request(url, token, unauth_error, status_code=401)
        return unauth_error
    return auth_request_bad_token

@pytest.fixture
def mock_kbase_server_error(requests_mock):
    def mock_generic_error(method: str, url: str, err: dict):
        requests_mock.register_uri(method, url, status_code=500, json=err)
    return mock_generic_error

def build_jsonrpc_1_response(result: dict, is_error: bool=False, no_result: bool=False):
    resp = {
        "id": "12345",
        "version": "1.1",
    }
    if no_result:
        return resp
    if is_error:
        resp["error"] = result
    else:
        resp["result"] = [result]
    return resp

def match_jsonrpc_1_packet(request):
    """
    Returns True if this looks like a KBase-ish JSON-RPC 1 packet.
    Should have the following:
    * id: string
    * version: string == 1.1
    * method: string == XXX.YYY
    * params: list
    """
    packet = request.json()
    if len(packet) != 4:
        return False
    if "params" not in packet or not isinstance(packet["params"], list):
        return False
    expected_strs = ["id", "version", "method"]
    for expected in expected_strs:
        if expected not in packet or not isinstance(packet[expected], str):
            return False
    return True

@pytest.fixture
def mock_kbase_jsonrpc_1_call(requests_mock):
    def kbase_jsonrpc_1_call(url: str, resp: dict, status_code: int=200, no_result: bool=False):
        is_error = status_code != 200
        response_packet = build_jsonrpc_1_response(resp, is_error=is_error, no_result=no_result)
        requests_mock.register_uri(
            "POST",
            url,
            additional_matcher=match_jsonrpc_1_packet,
            json=response_packet,
            headers={"content-type": "application/json"},
            status_code=status_code
        )
        return response_packet
    return kbase_jsonrpc_1_call

@pytest.fixture
def mock_kbase_client_call(requests_mock):
    def kbase_call(client: ServiceClient, resp: dict, service_method: str=None, status_code: int=200):
        def match_kbase_service_call(request):
            packet = request.json()
            if "method" not in packet or not isinstance(packet["method"], str):
                return False
            method = packet["method"].split(".")
            if len(method) != 2 or method[0] != client._service:
                return False
            if service_method is not None and service_method != method[1]:
                return False
            return match_jsonrpc_1_packet(request)

        is_error = status_code != 200
        response_packet = build_jsonrpc_1_response(resp, is_error=is_error)
        requests_mock.register_uri(
            "POST",
            client._endpoint,
            additional_matcher=match_kbase_service_call,
            json=response_packet,
            headers={"content-type": "application/json"},
            status_code=status_code
        )
        return response_packet
    return kbase_call

@pytest.fixture
def sample_narrative_json() -> str:
    # TODO
    # make a sample narrative JSON file (just download one)
    # make sure it has cells:
    # code, markdown, app, output, data, bulk import
    # open it and return the raw JSON str
    return get_test_narrative()

class MockLLM(LLM):
    def _call():
        pass

    def _llm_type():
        pass

@pytest.fixture
def mock_llm():
    return MockLLM()

@pytest.fixture
def mock_workspace(mocker: pytest.MonkeyPatch) -> Mock:
    ws = mocker.Mock(spec=Workspace)
    ws_data = load_test_data_json("fake_ws_data.json")

    def get_object_info_side_effect(ref: str, ):
        split_ref = ref.split("/")
        if len(split_ref) == 1:
            key = ref
        elif len(split_ref) == 2 or len(split_ref) == 3:
            key = split_ref[1]
        else:
            raise ServerError("WorkspaceError", 500, "Not a ref")  # TODO: make real error
        if key in ws_data["data"]:
            return ws_data["data"][key]
        else:
            raise ServerError("WorkspaceError", 500, "Not in ws")  # TODO: make real response
    ws.get_object_info.side_effect = get_object_info_side_effect
    ws.get_workspace_info.return_value = WorkspaceInfo(ws_data["info"])
    return ws

@pytest.fixture
def mock_job_states() -> dict[str, dict[str, any]]:
    return load_test_data_json("job_states.json")

@pytest.fixture
def app_spec() -> dict[str, any]:
    """
    Loads an app spec for testing. This is the NarrativeTest/test_input_params app spec.
    """
    app_spec_path = Path("app_spec_data") / "test_app_spec.json"
    spec = load_test_data_json(app_spec_path)
    return spec
