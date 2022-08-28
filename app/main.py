#!/usr/local/bin/python3
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

import asyncio
import datetime
import os
import socket
import time
from concurrent.futures import CancelledError

import sentry_sdk

import opcua
from opcua import Node
from opcua.ua import UaStatusCodeError
from opcua.ua.uaerrors import BadNodeIdUnknown
from opcua.ua.uatypes import AccessLevel, VariantType

from backend import Backend

if os.getenv('SENTRY_DSN') is not None:
    sentry_sdk.init(
        os.getenv('SENTRY_DSN'),
        traces_sample_rate=os.getenv('SENTRY_TRACES_SAMPLE_RATE', '1'),
    )

backend: Backend = Backend(
    os.getenv('API_URL', 'http://api/'),
    os.environ['ACCESS_TOKEN'],
)


def _handle_extension_object(
    value: VariantType.ExtensionObject,
    server_id: int,
    node_id: str,
    path: str,
    readable: bool,
    writable: bool,
    check_datetime: int,
):
    for key in value.__dict__:
        if isinstance(value.__dict__[key], bool):
            subtype = VariantType.Boolean
        elif isinstance(value.__dict__[key], float):
            subtype = VariantType.Float
        elif isinstance(value.__dict__[key], int):
            subtype = VariantType.Int16
        elif isinstance(value.__dict__[key], str):
            subtype = VariantType.String
        elif isinstance(value.__dict__[key], datetime.datetime):
            subtype = VariantType.DateTime
        else:
            return
        backend.create_or_update_node(
            server_id,
            node_id,
            key,
            path,
            readable,
            writable,
            subtype,
            check_datetime,
            virtual=True,
            parent_identifier=node_id,
        )


async def _discover_children(node: Node, server_id: int, opcua_client: opcua.Client, check_datetime: int) -> None:
    try:
        if node.nodeid.to_string() == 'i=84':
            path = '/'
        else:
            path = '/' + '/'.join(node.get_path(as_string=True))

    except UaStatusCodeError as error:  # type: ignore
        path = f"UaStatusCodeError({error.code})"
    except CancelledError:
        path = 'CancelledError'
    except AttributeError:
        pass
    except TypeError:
        pass

    try:
        node_id: str = node.nodeid.to_string()
        node: Node = opcua_client.get_node(node_id)
        writable = AccessLevel.CurrentWrite in node.get_user_access_level()
        readable = AccessLevel.CurrentRead in node.get_user_access_level()
        variant_type: VariantType = node.read_data_type_as_variant_type()

        try:
            display_name: str = node.read_display_name().Text
        except UaStatusCodeError as error:  # type: ignore
            display_name = f"UaStatusCodeError({error.code})"

        backend.create_or_update_node(
            server_id,
            node_id,
            display_name,
            path,
            readable,
            writable,
            variant_type,
            check_datetime,
        )

        if variant_type == VariantType.ExtensionObject:
            _handle_extension_object(
                node.get_value(),
                server_id,
                node_id,
                path,
                readable,
                writable,
                check_datetime
            )

    except UaStatusCodeError as error:  # type: ignore
        pass
    except AttributeError:
        pass
    except ValueError as error:
        print('value error')
        print(error)
    except TypeError as error:
        print('type error')
        print(error)
    except CancelledError as error:
        print('CancelledError')
        print(error)
    except BrokenPipeError as error:
        print('BrokenPipeError')
        print(error)

    children = node.get_children()
    for child_node in children:
        await _discover_children(child_node, server_id, opcua_client, check_datetime)


async def _handle_server(
    server_id: int,
    server_url: str,
    root_node_id: str,
    check_datetime: int
):
    opcua_client: opcua.Client = opcua.Client(server_url, timeout=30)

    try:
        opcua_client.connect()
        opcua_client.load_data_type_definitions()

        try:
            if root_node_id != '':
                root_node: Node = opcua_client.get_node(root_node_id)
            else:
                root_node: Node = opcua_client.get_root_node()
        except UaStatusCodeError as error:  # type: ignore
            if error.code == BadNodeIdUnknown.code:
                root_node: Node = opcua_client.get_root_node()

        _discover_children(root_node, server_id, opcua_client, check_datetime)

        backend.reset_server(server_id, check_datetime)
        backend.delete_outdated_nodes(server_id)

    except UaStatusCodeError as error:  # type: ignore
        backend.set_server_error(
            server_id, f"UaStatusCodeError({error.code})", check_datetime)
    except socket.gaierror as error:
        backend.set_server_error(server_id, 'socket.gaierror', check_datetime)
    finally:
        opcua_client.disconnect()


async def main():
    # wait for the backend to come online
    while not backend.available():
        time.sleep(30)

    # if a all servers are scanned seconds don't try again for 60 seconds
    update_interval: int = 60
    while True:
        check_datetime = int(time.time())
        for server in backend.get_servers():
            await _handle_server(
                server['id'],
                server['url'],
                server['root_node'],
                check_datetime,
            )
        await asyncio.sleep(update_interval)

if __name__ == '__main__':
    asyncio.run(main())
