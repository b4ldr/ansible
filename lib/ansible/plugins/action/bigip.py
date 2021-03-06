#
# (c) 2016 Red Hat Inc.
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import sys
import copy

from ansible import constants as C
from ansible.module_utils._text import to_text
from ansible.module_utils.connection import Connection
from ansible.module_utils.f5_utils import F5_COMMON_ARGS
from ansible.module_utils.network.common.utils import load_provider
from ansible.plugins.action.normal import ActionModule as _ActionModule

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class ActionModule(_ActionModule):

    def run(self, tmp=None, task_vars=None):
        transport = self._task.args.get('transport', 'rest')

        display.vvvv('connection transport is %s' % transport, self._play_context.remote_addr)

        if transport == 'cli':
            provider = load_provider(F5_COMMON_ARGS, self._task.args)
            self._task.args.pop('provider', None)
            pc = copy.deepcopy(self._play_context)
            pc.connection = 'network_cli'
            pc.network_os = 'bigip'
            pc.remote_addr = provider.get('server', self._play_context.remote_addr)
            pc.port = int(provider['server_port'] or self._play_context.port or 22)
            pc.remote_user = provider.get('user', self._play_context.connection_user)
            pc.password = provider.get('password', self._play_context.password)
            pc.timeout = int(provider.get('timeout', C.PERSISTENT_COMMAND_TIMEOUT))

            display.vvv('using connection plugin %s (was local)' % pc.connection, pc.remote_addr)
            connection = self._shared_loader_obj.connection_loader.get('persistent', pc, sys.stdin)

            socket_path = connection.run()
            display.vvvv('socket_path: %s' % socket_path, pc.remote_addr)
            if not socket_path:
                return {'failed': True,
                        'msg': 'unable to open shell. Please see: ' +
                               'https://docs.ansible.com/ansible/network_debug_troubleshooting.html#unable-to-open-shell'}

            # make sure we are in the right cli context which should be
            # enable mode and not config module
            conn = Connection(socket_path)
            out = conn.get_prompt()
            while '(config' in to_text(out, errors='surrogate_then_replace').strip():
                display.vvvv('wrong context, sending exit to device', self._play_context.remote_addr)
                conn.send_command('exit')
                out = conn.get_prompt()

            task_vars['ansible_socket'] = socket_path

        result = super(ActionModule, self).run(tmp, task_vars)
        return result
