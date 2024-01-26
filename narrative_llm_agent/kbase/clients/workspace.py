from ..service_client import ServiceClient
from typing import Any
from copy import deepcopy

class WorkspaceObjectId:
    upa: str
    ws_id: int
    obj_id: int
    version: int

    def __init__(self: "WorkspaceObjectId", upa: str):
        self.upa = upa
        self._process_upa()

    def _process_upa(self: "WorkspaceObjectId"):
        split_upa = self.upa.split("/")
        self.ws_id = int(split_upa[0])
        self.obj_id = int(split_upa[1])
        self.version = int(split_upa[2])

    @classmethod
    def from_upa(cls: "WorkspaceObjectId", upa: str) -> "WorkspaceObjectId":
        return cls(upa)

    @classmethod
    def from_ids(cls: "WorkspaceObjectId", ws_id: int, obj_id: int, version: int) -> "WorkspaceObjectId":
        return cls(f"{ws_id}/{obj_id}/{version}")

    def __repr__(self: "WorkspaceObjectId") -> str:
        return self.upa

    def __str__(self: "WorkspaceObjectId") -> str:
        return self.__repr__()


class WorkspaceObjectInfo:
    upa: WorkspaceObjectId
    raw: list[Any]
    name: str

    def __init__(self: "WorkspaceObjectInfo", info: list[Any]):
        self.upa = WorkspaceObjectId.from_ids(info[6], info[0], info[4])
        self.raw = info
        self.name = info[1]

    def __repr__(self: "WorkspaceObjectInfo") -> str:
        return f"{self.upa}\t{self.name}\n{self.raw}"


class Workspace:
    default_endpoint: str = "https://kbase.us/services/ws"
    _service = "Workspace"

    def __init__(self: "Workspace", token: str, endpoint: str=default_endpoint) -> "Workspace":
        self._token = token
        self._endpoint = endpoint
        self._client = ServiceClient(endpoint, self._service, token)

    def _call(self: "Workspace", method: str, params: Any) -> Any:
        """
        raises a requests.HTTPError if a failure happens.
        """
        return self._client.make_kbase_jsonrpc_1_call(method, [params])[0]

    def list_workspace_objects(self: "Workspace", ws_id: int, object_type: str=None, as_dict: bool=False) -> list[list]:
        ws_info = self._call("get_workspace_info", {"id": ws_id})
        max_obj_id = ws_info[4]
        chunk_size = 10000
        current_max = 0
        objects = []
        while current_max < max_obj_id:
            list_obj_params = {
                "ids": [ws_id],
                "minObjectID": current_max,
                "maxObjectID": current_max + chunk_size,
                "type": object_type
            }
            objects += self._call("list_objects", list_obj_params)
            current_max += chunk_size + 1
        if not as_dict:
            return objects
        return [self.obj_info_to_json(info) for info in objects]

    def get_object_upas(self: "Workspace", ws_id: int, object_type: str=None) -> list[WorkspaceObjectId]:
        obj_infos = self.list_workspace_objects(ws_id, object_type=object_type)
        return [WorkspaceObjectId.from_ids(info[6], info[0], info[4]) for info in obj_infos]

    def get_objects(self: "Workspace", upas: list[str], data_paths: list[str]=None) -> dict:
        base_params = {}
        if data_paths is not None:
            base_params["included"] = data_paths

        params_list = [dict(deepcopy(base_params)) | {"ref": upa} for upa in upas]
        return self._call("get_objects2", {"objects": params_list})["data"]

    @classmethod
    def obj_info_to_json(cls, obj_info: list[Any]) -> dict[str, Any]:
        return {
            "ws_id": obj_info[6],
            "obj_id": obj_info[0],
            "name": obj_info[1],
            "metadata": obj_info[10],
            "type": obj_info[2],
            "saved": obj_info[3],
            "version": obj_info[4],
            "saved_by": obj_info[5],
            "size_bytes": obj_info[9]
        }
