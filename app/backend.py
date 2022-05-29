# Copyright (C) 2022 Robin Jespersen
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import requests
from asyncua.ua.uatypes import VariantType


class Backend:
    API_URL: str
    ACCESS_TOKEN: str

    def __init__(self, api_url: str, access_token: str):
        self.API_URL = api_url
        self.ACCESS_TOKEN = access_token

    def available(self) -> bool:
        response = requests.get(f"{self.API_URL}/api/status/ping")
        return response.status_code == 200

    def reset_server(self, server_id: int, check_datetime: int):
        data = {
            'checked_at': check_datetime,
            'scan_required': 0,
        }
        requests.patch(
            f'{self.API_URL}/api/server_manager/server/update?id={server_id}',
            headers=self._get_headers(),
            data=data,
        )

    def delete_outdated_nodes(self, server_id: int):
        requests.post(
            f'{self.API_URL}/api/server_manager/node/delete-unchecked',
            headers=self._get_headers(),
            data={'server_id': server_id},
        )

    def create_or_update_node(
            self,
            server_id: int,
            node_id: str,
            display_name: str,
            path: str,
            readable: bool,
            writable: bool,
            variant_type: VariantType,
            check_datetime: int,
            virtual: bool = False,
            parent_identifier: str = None,
    ):
        variant_type_str = str(variant_type).split('.')[-1]

        data = {
            'server_id': server_id,
            'identifier': str(node_id) + '.' + str(display_name) if virtual else str(node_id),
        }

        response = requests.post(
            f'{self.API_URL}/api/server_manager/node/exists',
            headers=self._get_headers(),
            data=data,
        )
        tmp_node = response.json()

        data2 = {
            'server_id': int(server_id),
            'identifier': str(node_id) + '.' + str(display_name) if virtual else str(node_id),
            'display_name': str(display_name),
            'checked_at': check_datetime,
            'path': str(path),
            'readable': int(readable),
            'writable': int(writable),
            'data_type': variant_type_str,
            'virtual': int(virtual),
        }
        if parent_identifier is not None:
            data2['parent_identifier'] = parent_identifier
        if tmp_node is None:  # create it
            requests.post(
                f'{self.API_URL}/api/server_manager/node/create',
                headers=self._get_headers(),
                data=data2,
            )
        else:  # update it
            requests.patch(
                self.API_URL +
                '/api/server_manager/node/update?id=%s' % tmp_node['id'],
                headers=self._get_headers(),
                data=data2,
            )

    def set_server_error(self, server_id: int, error: str, check_datetime: int):
        data = {
            'has_connection_error': 1,
            'connection_error': error,
            'checked_at': check_datetime,  # hack
        }
        requests.patch(
            f'{self.API_URL}/api/server_manager/server/update?id={server_id}',
            headers=self._get_headers(),
            data=data,
        )

    def get_servers(self):
        response = requests.get(
            f'{self.API_URL}/api/server_manager/server/index?filter[scan_required]=1',
            headers=self._get_headers(),
        )
        return response.json()

    def _get_headers(self):
        return {"Authorization": f"Bearer {self.ACCESS_TOKEN}"}
