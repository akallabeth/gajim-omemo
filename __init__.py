# -*- coding: utf-8 -*-
# copyright 2015 bahtiar `kalkin-` gadimov <bahtiar@gadimov.de>
#
# this file is part of gajim.
#
# gajim is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published
# by the free software foundation; version 3 only.
#
# gajim is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with gajim.  if not, see <http://www.gnu.org/licenses/>.
#

from common import caps_cache, gajim, ged
from plugins import GajimPlugin
from plugins.helpers import log, log_calls

from .state import OmemoState
from .ui import OmemoButton

NS_OMEMO = 'eu.siacs.conversations.axolotl'
NS_DEVICE_LIST = NS_OMEMO + '.devicelist'
NS_NOTIFY = NS_DEVICE_LIST + '+notify'


class OmemoPlugin(GajimPlugin):

    omemo_states = {}

    @log_calls('OmemoPlugin')
    def init(self):
        self.events_handlers = {
            'message-received': (ged.CORE, self._pep_received)
        }
        self.config_dialog = None
        self.gui_extension_points = {'chat_control_base':
                                     (self.connect_ui, None)}
        for account in gajim.contacts.get_accounts():
            self.omemo_states[account] = OmemoState(account)

    @log_calls('OmemoPlugin')
    def activate(self):
        if NS_NOTIFY not in gajim.gajim_common_features:
            gajim.gajim_common_features.append(NS_NOTIFY)
        self._compute_caps_hash()

    @log_calls('OmemoPlugin')
    def deactivate(self):
        if NS_NOTIFY in gajim.gajim_common_features:
            gajim.gajim_common_features.remove(NS_NOTIFY)
        self._compute_caps_hash()

    @log_calls('OmemoPlugin')
    def _compute_caps_hash(self):
        for a in gajim.connections:
            gajim.caps_hash[a] = caps_cache.compute_caps_hash(
                [
                    gajim.gajim_identity
                ],
                gajim.gajim_common_features + gajim.gajim_optional_features[a])
            # re-send presence with new hash
            connected = gajim.connections[a].connected
            if connected > 1 and gajim.SHOW_LIST[connected] != 'invisible':
                gajim.connections[a].change_status(gajim.SHOW_LIST[connected],
                                                   gajim.connections[a].status)

    @log_calls('OmemoPlugin')
    def _pep_received(self, pep):

        event = pep.stanza.getTag('event')
        if not event:
            return

        items = pep.stanza.getTag('event').getTag('items', {'node':
                                                            NS_DEVICE_LIST})
        if items and len(items.getChildren()) == 1:

            account = pep.conn.name
            log.info(account + ' ⇒ Received OMEMO pep')

            devices = items.getChildren()[0].getTag('list').getChildren()
            devices_list = [dev.getAttr('id') for dev in devices]

            state = self.omemo_states[account]

            contact_jid = gajim.get_jid_without_resource(pep.fjid)
            my_jid = gajim.get_jid_without_resource(pep.jid)

            if contact_jid == my_jid:
                state.add_own_devices(devices_list)

                if not state.own_device_id_published():
                    # Our own device_id is not in the list, it could be
                    # overwritten by some other client?
                    devices_list.append(state.own_device_id)
                    self.publish_own_devices_list(state, devices_list)
            else:
                state.add_devices(contact_jid, devices_list)

    @log_calls('OmemoPlugin')
    def publish_own_devices_list(self, state, devices_list):
        log.info(state.name + ' ⇒ Publishing own device_list ' + str(
            devices_list))

    @log_calls('OmemoPlugin')
    def connect_ui(self, chat_control):
        actions_hbox = chat_control.xml.get_object('actions_hbox')
        send_button = chat_control.xml.get_object('send_button')
        send_button_pos = actions_hbox.child_get_property(send_button,
                                                          'position')
        button = OmemoButton(self, chat_control.contact)
        actions_hbox.add_with_properties(button, 'position',
                                         send_button_pos - 2, 'expand', False)

    @log_calls('OmemoPlugin')
    def device_ids_for(self, contact):
        account = contact.account.name
        if account not in self.device_ids:
            log.debug('Account:' + str(account) + '¬∈ devices_ids')
            return None
        contact_jid = gajim.get_jid_without_resource(contact.get_full_jid())
        if contact_jid not in self.device_ids[account]:
            log.debug('Contact:' + contact_jid + '¬∈ devices_ids[' + account +
                      ']')
            return None

        log.info(self.device_ids[account])
        return self.device_ids[account][contact_jid]
