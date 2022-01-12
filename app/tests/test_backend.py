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

from backend import Backend
import time
import httpretty
import unittest


class TestBackend(unittest.TestCase):
    backend: Backend

    def setUp(self):
        self.backend = Backend('http://test-server', 'test-token')

    @httpretty.activate(verbose=True, allow_net_connect=False)
    def test_available(self):
        httpretty.register_uri(
            httpretty.GET,
            'http://test-server/api/status/ping',
            status=200
        )
        self.assertTrue(self.backend.available())

        httpretty.register_uri(
            httpretty.GET,
            'http://test-server/api/status/ping',
            status=404
        )
        self.assertFalse(self.backend.available())

    @httpretty.activate(verbose=True, allow_net_connect=False)
    def test_reset_server(self):
        httpretty.register_uri(
            httpretty.PATCH,
            'http://test-server/api/server_manager/server/update',
            status=200,
        )
        now: int = int(time.time())
        self.backend.reset_server(4, now)
        latest: httpretty.core.HTTPrettyRequest = httpretty.latest_requests()[
            0]
        self.assertTrue(f'checked_at={now}' in str(latest.body))
        self.assertTrue('scan_required=0' in str(latest.body))

    @httpretty.activate(verbose=True, allow_net_connect=False)
    def test_delete_outdated_nodes(self):
        httpretty.register_uri(
            httpretty.POST,
            'http://test-server/api/server_manager/node/delete-unchecked',
            status=200,
        )
        self.backend.delete_outdated_nodes(7)
        latest: httpretty.core.HTTPrettyRequest = httpretty.latest_requests()[
            0]
        self.assertTrue('server_id=7' in str(latest.body))

    @httpretty.activate(verbose=True, allow_net_connect=False)
    def test_create_or_update_node(self):
        pass  # TODO

    @httpretty.activate(verbose=True, allow_net_connect=False)
    def test_set_server_error(self):
        httpretty.register_uri(
            httpretty.PATCH,
            'http://test-server/api/server_manager/server/update',
            status=200,
        )
        now: int = int(time.time())
        self.backend.set_server_error(3, 'test_error', now)
        latest: httpretty.core.HTTPrettyRequest = httpretty.latest_requests()[
            0]
        self.assertEqual(latest.headers['Authorization'], 'Bearer test-token')
        self.assertEqual(latest.querystring['id'][0], '3')
        self.assertTrue(f'checked_at={now}' in str(latest.body))
        self.assertTrue('connection_error=test_error' in str(latest.body))
        self.assertTrue('has_connection_error=1' in str(latest.body))

    @httpretty.activate(verbose=True, allow_net_connect=False)
    def test_get_servers(self):
        httpretty.register_uri(
            httpretty.GET,
            'http://test-server/api/server_manager/server/index',
            status=200,
            body='{}'
        )
        self.backend.get_servers()
        latest: httpretty.core.HTTPrettyRequest = httpretty.latest_requests()[
            0]
        self.assertEqual(latest.headers['Authorization'], 'Bearer test-token')


if __name__ == '__main__':
    unittest.main()
