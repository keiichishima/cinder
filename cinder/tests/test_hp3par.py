#
#    (c) Copyright 2013 Hewlett-Packard Development Company, L.P.
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""Unit tests for OpenStack Cinder volume drivers."""

import mock

from cinder import context
from cinder import exception
from cinder.openstack.common import log as logging
from cinder.openstack.common import units
from cinder import test

from cinder.tests import fake_hp_3par_client as hp3parclient
from cinder.volume.drivers.san.hp import hp_3par_fc as hpfcdriver
from cinder.volume.drivers.san.hp import hp_3par_iscsi as hpdriver
from cinder.volume import qos_specs
from cinder.volume import volume_types

hpexceptions = hp3parclient.hpexceptions

LOG = logging.getLogger(__name__)

HP3PAR_CPG = 'OpenStackCPG'
HP3PAR_CPG_SNAP = 'OpenStackCPGSnap'
HP3PAR_USER_NAME = 'testUser'
HP3PAR_USER_PASS = 'testPassword'
HP3PAR_SAN_IP = '2.2.2.2'
HP3PAR_SAN_SSH_PORT = 999
HP3PAR_SAN_SSH_CON_TIMEOUT = 44
HP3PAR_SAN_SSH_PRIVATE = 'foobar'


class HP3PARBaseDriver(object):

    VOLUME_ID = 'd03338a9-9115-48a3-8dfc-35cdfcdc15a7'
    CLONE_ID = 'd03338a9-9115-48a3-8dfc-000000000000'
    VOLUME_NAME = 'volume-' + VOLUME_ID
    VOLUME_NAME_3PAR = 'osv-0DM4qZEVSKON-DXN-NwVpw'
    SNAPSHOT_ID = '2f823bdc-e36e-4dc8-bd15-de1c7a28ff31'
    SNAPSHOT_NAME = 'snapshot-2f823bdc-e36e-4dc8-bd15-de1c7a28ff31'
    VOLUME_3PAR_NAME = 'osv-0DM4qZEVSKON-DXN-NwVpw'
    SNAPSHOT_3PAR_NAME = 'oss-L4I73ONuTci9Fd4ceij-MQ'
    FAKE_HOST = 'fakehost'
    USER_ID = '2689d9a913974c008b1d859013f23607'
    PROJECT_ID = 'fac88235b9d64685a3530f73e490348f'
    VOLUME_ID_SNAP = '761fc5e5-5191-4ec7-aeba-33e36de44156'
    FAKE_DESC = 'test description name'
    FAKE_FC_PORTS = [{'portPos': {'node': 7, 'slot': 1, 'cardPort': 1},
                      'portWWN': '0987654321234',
                      'protocol': 1,
                      'mode': 2,
                      'linkState': 4},
                     {'portPos': {'node': 6, 'slot': 1, 'cardPort': 1},
                      'portWWN': '123456789000987',
                      'protocol': 1,
                      'mode': 2,
                      'linkState': 4}]
    QOS = {'qos:maxIOPS': '1000', 'qos:maxBWS': '50',
           'qos:minIOPS': '100', 'qos:minBWS': '25',
           'qos:latency': '25', 'qos:priority': 'low'}
    QOS_SPECS = {'maxIOPS': '1000', 'maxBWS': '50',
                 'minIOPS': '100', 'minBWS': '25',
                 'latency': '25', 'priority': 'low'}
    VVS_NAME = "myvvs"
    FAKE_ISCSI_PORT = {'portPos': {'node': 8, 'slot': 1, 'cardPort': 1},
                       'protocol': 2,
                       'mode': 2,
                       'IPAddr': '1.1.1.2',
                       'iSCSIName': ('iqn.2000-05.com.3pardata:'
                                     '21810002ac00383d'),
                       'linkState': 4}
    volume = {'name': VOLUME_NAME,
              'id': VOLUME_ID,
              'display_name': 'Foo Volume',
              'size': 2,
              'host': FAKE_HOST,
              'volume_type': None,
              'volume_type_id': None}

    volume_qos = {'name': VOLUME_NAME,
                  'id': VOLUME_ID,
                  'display_name': 'Foo Volume',
                  'size': 2,
                  'host': FAKE_HOST,
                  'volume_type': None,
                  'volume_type_id': 'gold'}

    snapshot = {'name': SNAPSHOT_NAME,
                'id': SNAPSHOT_ID,
                'user_id': USER_ID,
                'project_id': PROJECT_ID,
                'volume_id': VOLUME_ID_SNAP,
                'volume_name': VOLUME_NAME,
                'status': 'creating',
                'progress': '0%',
                'volume_size': 2,
                'display_name': 'fakesnap',
                'display_description': FAKE_DESC}

    wwn = ["123456789012345", "123456789054321"]

    connector = {'ip': '10.0.0.2',
                 'initiator': 'iqn.1993-08.org.debian:01:222',
                 'wwpns': [wwn[0], wwn[1]],
                 'wwnns': ["223456789012345", "223456789054321"],
                 'host': FAKE_HOST}

    volume_type = {'name': 'gold',
                   'deleted': False,
                   'updated_at': None,
                   'extra_specs': {'qos:maxIOPS': '1000',
                                   'qos:maxBWS': '50',
                                   'qos:minIOPS': '100',
                                   'qos:minBWS': '25',
                                   'qos:latency': '25',
                                   'qos:priority': 'low'},
                   'deleted_at': None,
                   'id': 'gold'}

    cpgs = [
        {'SAGrowth': {'LDLayout': {'diskPatterns': [{'diskType': 2}]},
                      'incrementMiB': 8192},
         'SAUsage': {'rawTotalMiB': 24576,
                     'rawUsedMiB': 768,
                     'totalMiB': 8192,
                     'usedMiB': 256},
         'SDGrowth': {'LDLayout': {'RAIDType': 4,
                      'diskPatterns': [{'diskType': 2}]},
                      'incrementMiB': 32768},
         'SDUsage': {'rawTotalMiB': 49152,
                     'rawUsedMiB': 1023,
                     'totalMiB': 36864,
                     'usedMiB': 768},
         'UsrUsage': {'rawTotalMiB': 57344,
                      'rawUsedMiB': 43349,
                      'totalMiB': 43008,
                      'usedMiB': 32512},
         'additionalStates': [],
         'degradedStates': [],
         'failedStates': [],
         'id': 5,
         'name': HP3PAR_CPG,
         'numFPVVs': 2,
         'numTPVVs': 0,
         'state': 1,
         'uuid': '29c214aa-62b9-41c8-b198-543f6cf24edf'}]

    mock_client_conf = {
        'PORT_MODE_TARGET': 2,
        'PORT_STATE_READY': 4,
        'PORT_PROTO_ISCSI': 2,
        'PORT_PROTO_FC': 1,
        'TASK_DONE': 1,
        'HOST_EDIT_ADD': 1,
        'getPorts.return_value': {
            'members': FAKE_FC_PORTS + [FAKE_ISCSI_PORT]
        }
    }

    def setup_configuration(self):
        configuration = mock.Mock()
        configuration.hp3par_debug = False
        configuration.hp3par_username = HP3PAR_USER_NAME
        configuration.hp3par_password = HP3PAR_USER_PASS
        configuration.hp3par_api_url = 'https://1.1.1.1/api/v1'
        configuration.hp3par_cpg = HP3PAR_CPG
        configuration.hp3par_cpg_snap = HP3PAR_CPG_SNAP
        configuration.iscsi_ip_address = '1.1.1.2'
        configuration.iscsi_port = '1234'
        configuration.san_ip = HP3PAR_SAN_IP
        configuration.san_login = HP3PAR_USER_NAME
        configuration.san_password = HP3PAR_USER_PASS
        configuration.san_ssh_port = HP3PAR_SAN_SSH_PORT
        configuration.ssh_conn_timeout = HP3PAR_SAN_SSH_CON_TIMEOUT
        configuration.san_private_key = HP3PAR_SAN_SSH_PRIVATE
        configuration.hp3par_snapshot_expiration = ""
        configuration.hp3par_snapshot_retention = ""
        configuration.hp3par_iscsi_ips = []
        return configuration

    @mock.patch(
        'hp3parclient.client.HP3ParClient',
        spec=True,
    )
    def setup_mock_client(self, _m_client, driver, conf=None, m_conf=None):

        _m_client = _m_client.return_value

        # Configure the base constants, defaults etc...
        _m_client.configure_mock(**self.mock_client_conf)

        # If m_conf, drop those over the top of the base_conf.
        if m_conf is not None:
            _m_client.configure_mock(**m_conf)

        if conf is None:
            conf = self.setup_configuration()
        self.driver = driver(configuration=conf)
        self.driver.do_setup(None)
        return _m_client

    def test_create_volume(self):

        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        self.driver.create_volume(self.volume)
        comment = (
            '{"display_name": "Foo Volume", "type": "OpenStack",'
            ' "name": "volume-d03338a9-9115-48a3-8dfc-35cdfcdc15a7",'
            ' "volume_id": "d03338a9-9115-48a3-8dfc-35cdfcdc15a7"}')
        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.createVolume(
                self.VOLUME_3PAR_NAME,
                HP3PAR_CPG,
                1907, {
                    'comment': comment,
                    'tpvv': True,
                    'snapCPG': HP3PAR_CPG_SNAP}),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

    @mock.patch.object(volume_types, 'get_volume_type')
    def test_create_volume_qos(self, _mock_volume_types):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        _mock_volume_types.return_value = {
            'name': 'gold',
            'extra_specs': {
                'cpg': HP3PAR_CPG,
                'snap_cpg': HP3PAR_CPG_SNAP,
                'vvs_name': self.VVS_NAME,
                'qos': self.QOS,
                'tpvv': True,
                'volume_type': self.volume_type}}

        self.driver.create_volume(self.volume_qos)
        comment = (
            '{"volume_type_name": "gold", "display_name": "Foo Volume"'
            ', "name": "volume-d03338a9-9115-48a3-8dfc-35cdfcdc15a7'
            '", "volume_type_id": "gold", "volume_id": "d03338a9-91'
            '15-48a3-8dfc-35cdfcdc15a7", "qos": {}, "type": "OpenStack"}')

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.createVolume(
                self.VOLUME_3PAR_NAME,
                HP3PAR_CPG,
                1907, {
                    'comment': comment,
                    'tpvv': True,
                    'snapCPG': HP3PAR_CPG_SNAP}),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

    def test_delete_volume(self):

        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        self.driver.delete_volume(self.volume)

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.deleteVolume(self.VOLUME_3PAR_NAME),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

    def test_create_cloned_volume(self):

        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        mock_client.copyVolume.return_value = {'taskid': 1}

        volume = {'name': HP3PARBaseDriver.VOLUME_NAME,
                  'id': HP3PARBaseDriver.CLONE_ID,
                  'display_name': 'Foo Volume',
                  'size': 2,
                  'host': HP3PARBaseDriver.FAKE_HOST,
                  'source_volid': HP3PARBaseDriver.VOLUME_ID}
        src_vref = {}
        model_update = self.driver.create_cloned_volume(volume, src_vref)
        self.assertIsNotNone(model_update)

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.copyVolume(
                self.VOLUME_3PAR_NAME,
                'osv-0DM4qZEVSKON-AAAAAAAAA',
                HP3PAR_CPG,
                {'snapCPG': 'OpenStackCPGSnap', 'tpvv': True,
                 'online': True}),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

    def test_migrate_volume(self):

        conf = {
            'getStorageSystemInfo.return_value': {
                'serialNumber': '1234'},
            'getTask.return_value': {
                'status': 1},
            'getCPG.return_value': {},
            'copyVolume.return_value': {'taskid': 1},
            'getVolume.return_value': {}
        }

        mock_client = self.setup_driver(mock_conf=conf)

        volume = {'name': HP3PARBaseDriver.VOLUME_NAME,
                  'id': HP3PARBaseDriver.CLONE_ID,
                  'display_name': 'Foo Volume',
                  'size': 2,
                  'status': 'available',
                  'host': HP3PARBaseDriver.FAKE_HOST,
                  'source_volid': HP3PARBaseDriver.VOLUME_ID}

        volume_name_3par = self.driver.common._encode_name(volume['id'])

        loc_info = 'HP3PARDriver:1234:CPG-FC1'
        host = {'host': 'stack@3parfc1',
                'capabilities': {'location_info': loc_info}}

        result = self.driver.migrate_volume(context.get_admin_context(),
                                            volume, host)
        self.assertIsNotNone(result)
        self.assertEqual((True, None), result)

        osv_matcher = 'osv-' + volume_name_3par
        omv_matcher = 'omv-' + volume_name_3par

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getStorageSystemInfo(),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getCPG('CPG-FC1'),
            mock.call.copyVolume(osv_matcher, omv_matcher, mock.ANY, mock.ANY),
            mock.call.getTask(mock.ANY),
            mock.call.getVolume(osv_matcher),
            mock.call.deleteVolume(osv_matcher),
            mock.call.modifyVolume(omv_matcher, {'newName': osv_matcher}),
            mock.call.logout()
        ]

        mock_client.assert_has_calls(expected)

    def test_migrate_volume_diff_host(self):
        conf = {
            'getStorageSystemInfo.return_value': {
                'serialNumber': 'different'},
        }

        self.setup_driver(mock_conf=conf)

        volume = {'name': HP3PARBaseDriver.VOLUME_NAME,
                  'id': HP3PARBaseDriver.CLONE_ID,
                  'display_name': 'Foo Volume',
                  'size': 2,
                  'status': 'available',
                  'host': HP3PARBaseDriver.FAKE_HOST,
                  'source_volid': HP3PARBaseDriver.VOLUME_ID}

        loc_info = 'HP3PARDriver:1234:CPG-FC1'
        host = {'host': 'stack@3parfc1',
                'capabilities': {'location_info': loc_info}}

        result = self.driver.migrate_volume(context.get_admin_context(),
                                            volume, host)
        self.assertIsNotNone(result)
        self.assertEqual((False, None), result)

    def test_migrate_volume_diff_domain(self):
        conf = {
            'getStorageSystemInfo.return_value': {
                'serialNumber': '1234'},
            'getTask.return_value': {
                'status': 1},
            'getCPG.side_effect':
            lambda x: {'OpenStackCPG': {'domain': 'OpenStack'}}.get(x, {})
        }

        self.setup_driver(mock_conf=conf)

        volume = {'name': HP3PARBaseDriver.VOLUME_NAME,
                  'id': HP3PARBaseDriver.CLONE_ID,
                  'display_name': 'Foo Volume',
                  'size': 2,
                  'status': 'available',
                  'host': HP3PARBaseDriver.FAKE_HOST,
                  'source_volid': HP3PARBaseDriver.VOLUME_ID}

        loc_info = 'HP3PARDriver:1234:CPG-FC1'
        host = {'host': 'stack@3parfc1',
                'capabilities': {'location_info': loc_info}}

        result = self.driver.migrate_volume(context.get_admin_context(),
                                            volume, host)
        self.assertIsNotNone(result)
        self.assertEqual((False, None), result)

    def test_migrate_volume_attached(self):

        mock_client = self.setup_driver()

        volume = {'name': HP3PARBaseDriver.VOLUME_NAME,
                  'id': HP3PARBaseDriver.CLONE_ID,
                  'display_name': 'Foo Volume',
                  'size': 2,
                  'status': 'in-use',
                  'host': HP3PARBaseDriver.FAKE_HOST,
                  'source_volid': HP3PARBaseDriver.VOLUME_ID}

        volume_name_3par = self.driver.common._encode_name(volume['id'])

        mock_client.getVLUNs.return_value = {
            'members': [{'volumeName': 'osv-' + volume_name_3par}]}

        loc_info = 'HP3PARDriver:1234:CPG-FC1'
        host = {'host': 'stack@3parfc1',
                'capabilities': {'location_info': loc_info}}

        result = self.driver.migrate_volume(context.get_admin_context(),
                                            volume, host)
        self.assertIsNotNone(result)
        self.assertEqual((False, None), result)

    def test_attach_volume(self):

        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        self.driver.attach_volume(context.get_admin_context(),
                                  self.volume,
                                  'abcdef',
                                  'newhost',
                                  '/dev/vdb')

        expected = [
            mock.call.setVolumeMetaData(
                self.VOLUME_3PAR_NAME,
                'HPQ-CS-instance_uuid',
                'abcdef')]

        mock_client.assert_has_calls(expected)

        # test the exception
        mock_client.setVolumeMetaData.side_effect = Exception('Custom ex')
        self.assertRaises(exception.CinderException,
                          self.driver.attach_volume,
                          context.get_admin_context(),
                          self.volume,
                          'abcdef',
                          'newhost',
                          '/dev/vdb')

    def test_detach_volume(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        self.driver.detach_volume(context.get_admin_context(), self.volume)
        expected = [
            mock.call.removeVolumeMetaData(
                self.VOLUME_3PAR_NAME,
                'HPQ-CS-instance_uuid')]

        mock_client.assert_has_calls(expected)

        # test the exception
        mock_client.removeVolumeMetaData.side_effect = Exception('Custom ex')
        self.assertRaises(exception.CinderException,
                          self.driver.detach_volume,
                          context.get_admin_context(),
                          self.volume)

    def test_create_snapshot(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        self.driver.create_snapshot(self.snapshot)

        commet = (
            '{"volume_id": "761fc5e5-5191-4ec7-aeba-33e36de44156",'
            ' "display_name": "fakesnap",'
            ' "description": "test description name",'
            ' "volume_name": "volume-d03338a9-9115-48a3-8dfc-35cdfcdc15a7"}')

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.createSnapshot(
                'oss-L4I73ONuTci9Fd4ceij-MQ',
                'osv-dh-F5VGRTseuujPjbeRBVg',
                {
                    'comment': commet,
                    'readOnly': True}),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

    def test_delete_snapshot(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        self.driver.delete_snapshot(self.snapshot)

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.deleteVolume('oss-L4I73ONuTci9Fd4ceij-MQ'),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

    def test_delete_snapshot_in_use(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        self.driver.create_snapshot(self.snapshot)
        self.driver.create_volume_from_snapshot(self.volume, self.snapshot)

        ex = hpexceptions.HTTPConflict("In use")
        mock_client.deleteVolume = mock.Mock(side_effect=ex)

        # Deleting the snapshot that a volume is dependent on should fail
        self.assertRaises(exception.SnapshotIsBusy,
                          self.driver.delete_snapshot,
                          self.snapshot)

    def test_delete_snapshot_not_found(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        self.driver.create_snapshot(self.snapshot)

        try:
            ex = hpexceptions.HTTPNotFound("not found")
            mock_client.deleteVolume = mock.Mock(side_effect=ex)
            self.driver.delete_snapshot(self.snapshot)
        except Exception:
            self.fail("Deleting a snapshot that is missing should act as if "
                      "it worked.")

    def test_create_volume_from_snapshot(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        self.driver.create_volume_from_snapshot(self.volume, self.snapshot)

        comment = (
            '{"snapshot_id": "2f823bdc-e36e-4dc8-bd15-de1c7a28ff31",'
            ' "display_name": "Foo Volume",'
            ' "volume_id": "d03338a9-9115-48a3-8dfc-35cdfcdc15a7"}')

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.createSnapshot(
                self.VOLUME_3PAR_NAME,
                'oss-L4I73ONuTci9Fd4ceij-MQ',
                {
                    'comment': comment,
                    'readOnly': False}),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

        volume = self.volume.copy()
        volume['size'] = 1
        self.assertRaises(exception.InvalidInput,
                          self.driver.create_volume_from_snapshot,
                          volume, self.snapshot)

    def test_create_volume_from_snapshot_and_extend(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        conf = {
            'getTask.return_value': {
                'status': 1},
            'copyVolume.return_value': {'taskid': 1},
            'getVolume.return_value': {}
        }

        mock_client = self.setup_driver(mock_conf=conf)

        volume = self.volume.copy()
        volume['size'] = self.volume['size'] + 10
        self.driver.create_volume_from_snapshot(volume, self.snapshot)

        comment = (
            '{"snapshot_id": "2f823bdc-e36e-4dc8-bd15-de1c7a28ff31",'
            ' "display_name": "Foo Volume",'
            ' "volume_id": "d03338a9-9115-48a3-8dfc-35cdfcdc15a7"}')

        volume_name_3par = self.driver.common._encode_name(volume['id'])
        osv_matcher = 'osv-' + volume_name_3par
        omv_matcher = 'omv-' + volume_name_3par

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.createSnapshot(
                self.VOLUME_3PAR_NAME,
                'oss-L4I73ONuTci9Fd4ceij-MQ',
                {
                    'comment': comment,
                    'readOnly': False}),
            mock.call.copyVolume(osv_matcher, omv_matcher, mock.ANY, mock.ANY),
            mock.call.getTask(mock.ANY),
            mock.call.getVolume(osv_matcher),
            mock.call.deleteVolume(osv_matcher),
            mock.call.modifyVolume(omv_matcher, {'newName': osv_matcher}),
            mock.call.growVolume(osv_matcher, 10 * 1024),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

    def test_create_volume_from_snapshot_and_extend_copy_fail(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        conf = {
            'getTask.return_value': {
                'status': 4,
                'failure message': 'out of disk space'},
            'copyVolume.return_value': {'taskid': 1},
            'getVolume.return_value': {}
        }

        self.setup_driver(mock_conf=conf)

        volume = self.volume.copy()
        volume['size'] = self.volume['size'] + 10

        self.assertRaises(exception.CinderException,
                          self.driver.create_volume_from_snapshot,
                          volume, self.snapshot)

    @mock.patch.object(volume_types, 'get_volume_type')
    def test_create_volume_from_snapshot_qos(self, _mock_volume_types):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        _mock_volume_types.return_value = {
            'name': 'gold',
            'extra_specs': {
                'cpg': HP3PAR_CPG,
                'snap_cpg': HP3PAR_CPG_SNAP,
                'vvs_name': self.VVS_NAME,
                'qos': self.QOS,
                'tpvv': True,
                'volume_type': self.volume_type}}
        self.driver.create_volume_from_snapshot(self.volume_qos, self.snapshot)

        comment = (
            '{"snapshot_id": "2f823bdc-e36e-4dc8-bd15-de1c7a28ff31",'
            ' "display_name": "Foo Volume",'
            ' "volume_id": "d03338a9-9115-48a3-8dfc-35cdfcdc15a7"}')

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.createSnapshot(
                self.VOLUME_3PAR_NAME,
                'oss-L4I73ONuTci9Fd4ceij-MQ', {
                    'comment': comment,
                    'readOnly': False}),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

        volume = self.volume.copy()
        volume['size'] = 1
        self.assertRaises(exception.InvalidInput,
                          self.driver.create_volume_from_snapshot,
                          volume, self.snapshot)

    def test_terminate_connection(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        mock_client.getHostVLUNs.return_value = [
            {'active': True,
             'volumeName': self.VOLUME_3PAR_NAME,
             'lun': None, 'type': 0}]

        self.driver.terminate_connection(
            self.volume,
            self.connector,
            force=True)

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getHostVLUNs(self.FAKE_HOST),
            mock.call.deleteVLUN(
                self.VOLUME_3PAR_NAME,
                None,
                self.FAKE_HOST),
            mock.call.deleteHost(self.FAKE_HOST),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

    def test_update_volume_key_value_pair(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        key = 'a'
        value = 'b'
        self.driver.common.update_volume_key_value_pair(
            self.volume,
            key,
            value)

        expected = [
            mock.call.setVolumeMetaData(self.VOLUME_3PAR_NAME, key, value)]

        mock_client.assert_has_calls(expected)

        # check exception
        mock_client.setVolumeMetaData.side_effect = Exception('fake')
        self.assertRaises(exception.VolumeBackendAPIException,
                          self.driver.common.update_volume_key_value_pair,
                          self.volume,
                          None,
                          'b')

    def test_clear_volume_key_value_pair(self):

        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        key = 'a'
        self.driver.common.clear_volume_key_value_pair(self.volume, key)

        expected = [
            mock.call.removeVolumeMetaData(self.VOLUME_3PAR_NAME, key)]

        mock_client.assert_has_calls(expected)

        # check the exception
        mock_client.removeVolumeMetaData.side_effect = Exception('fake')
        self.assertRaises(exception.VolumeBackendAPIException,
                          self.driver.common.clear_volume_key_value_pair,
                          self.volume,
                          None)

    def test_extend_volume(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        grow_size = 3
        old_size = self.volume['size']
        new_size = old_size + grow_size
        self.driver.extend_volume(self.volume, str(new_size))
        growth_size_mib = grow_size * units.Ki

        expected = [
            mock.call.growVolume(self.VOLUME_3PAR_NAME, growth_size_mib)]

        mock_client.assert_has_calls(expected)

    def test_extend_volume_non_base(self):
        extend_ex = hpexceptions.HTTPForbidden(error={'code': 150})
        conf = {
            'getTask.return_value': {
                'status': 1},
            'getCPG.return_value': {},
            'copyVolume.return_value': {'taskid': 1},
            'getVolume.return_value': {},
            # Throw an exception first time only
            'growVolume.side_effect': [extend_ex,
                                       None],
        }

        mock_client = self.setup_driver(mock_conf=conf)
        grow_size = 3
        old_size = self.volume['size']
        new_size = old_size + grow_size
        self.driver.extend_volume(self.volume, str(new_size))

        self.assertEqual(2, mock_client.growVolume.call_count)

    def test_extend_volume_non_base_failure(self):
        extend_ex = hpexceptions.HTTPForbidden(error={'code': 150})
        conf = {
            'getTask.return_value': {
                'status': 1},
            'getCPG.return_value': {},
            'copyVolume.return_value': {'taskid': 1},
            'getVolume.return_value': {},
            # Always fail
            'growVolume.side_effect': extend_ex
        }

        self.setup_driver(mock_conf=conf)
        grow_size = 3
        old_size = self.volume['size']
        new_size = old_size + grow_size
        self.assertRaises(hpexceptions.HTTPForbidden,
                          self.driver.extend_volume,
                          self.volume,
                          str(new_size))

    def test_get_ports(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        mock_client.getPorts.return_value = {
            'members': [
                {'portPos': {'node': 0, 'slot': 8, 'cardPort': 2},
                 'protocol': 2,
                 'IPAddr': '10.10.120.252',
                 'linkState': 4,
                 'device': [],
                 'iSCSIName': 'iqn.2000-05.com.3pardata:21810002ac00383d',
                 'mode': 2,
                 'HWAddr': '2C27D75375D2',
                 'type': 8},
                {'portPos': {'node': 1, 'slot': 8, 'cardPort': 1},
                 'protocol': 2,
                 'IPAddr': '10.10.220.253',
                 'linkState': 4,
                 'device': [],
                 'iSCSIName': 'iqn.2000-05.com.3pardata:21810002ac00383d',
                 'mode': 2,
                 'HWAddr': '2C27D75375D6',
                 'type': 8},
                {'portWWN': '20210002AC00383D',
                 'protocol': 1,
                 'linkState': 4,
                 'mode': 2,
                 'device': ['cage2'],
                 'nodeWWN': '20210002AC00383D',
                 'type': 2,
                 'portPos': {'node': 0, 'slot': 6, 'cardPort': 3}}]}

        ports = self.driver.common.get_ports()['members']
        self.assertEqual(len(ports), 3)

    def test_get_by_qos_spec_with_scoping(self):
        self.setup_driver()
        qos_ref = qos_specs.create(self.ctxt, 'qos-specs-1', self.QOS)
        type_ref = volume_types.create(self.ctxt,
                                       "type1", {"qos:maxIOPS": "100",
                                                 "qos:maxBWS": "50",
                                                 "qos:minIOPS": "10",
                                                 "qos:minBWS": "20",
                                                 "qos:latency": "5",
                                                 "qos:priority": "high"})
        qos_specs.associate_qos_with_type(self.ctxt,
                                          qos_ref['id'],
                                          type_ref['id'])
        type_ref = volume_types.get_volume_type(self.ctxt, type_ref['id'])
        qos = self.driver.common._get_qos_by_volume_type(type_ref)
        self.assertEqual(qos, {'maxIOPS': '1000', 'maxBWS': '50',
                               'minIOPS': '100', 'minBWS': '25',
                               'latency': '25', 'priority': 'low'})

    def test_get_by_qos_spec(self):
        self.setup_driver()
        qos_ref = qos_specs.create(self.ctxt, 'qos-specs-1', self.QOS_SPECS)
        type_ref = volume_types.create(self.ctxt,
                                       "type1", {"qos:maxIOPS": "100",
                                                 "qos:maxBWS": "50",
                                                 "qos:minIOPS": "10",
                                                 "qos:minBWS": "20",
                                                 "qos:latency": "5",
                                                 "qos:priority": "high"})
        qos_specs.associate_qos_with_type(self.ctxt,
                                          qos_ref['id'],
                                          type_ref['id'])
        type_ref = volume_types.get_volume_type(self.ctxt, type_ref['id'])
        qos = self.driver.common._get_qos_by_volume_type(type_ref)
        self.assertEqual(qos, {'maxIOPS': '1000', 'maxBWS': '50',
                               'minIOPS': '100', 'minBWS': '25',
                               'latency': '25', 'priority': 'low'})

    def test_get_by_qos_by_type_only(self):
        self.setup_driver()
        type_ref = volume_types.create(self.ctxt,
                                       "type1", {"qos:maxIOPS": "100",
                                                 "qos:maxBWS": "50",
                                                 "qos:minIOPS": "10",
                                                 "qos:minBWS": "20",
                                                 "qos:latency": "5",
                                                 "qos:priority": "high"})
        type_ref = volume_types.get_volume_type(self.ctxt, type_ref['id'])
        qos = self.driver.common._get_qos_by_volume_type(type_ref)
        self.assertEqual(qos, {'maxIOPS': '100', 'maxBWS': '50',
                               'minIOPS': '10', 'minBWS': '20',
                               'latency': '5', 'priority': 'high'})

    def test_create_vlun(self):
        host = 'fake-host'
        lun_id = 11
        nsp = '1:2:3'
        mock_client = self.setup_driver()
        location = ("%(name)s,%(lunid)s,%(host)s,%(nsp)s" %
                    {'name': self.VOLUME_NAME,
                     'lunid': lun_id,
                     'host': host,
                     'nsp': nsp})
        mock_client.createVLUN.return_value = location

        expected_info = {'volume_name': self.VOLUME_NAME,
                         'lun_id': lun_id,
                         'host_name': host,
                         'nsp': nsp}
        vlun_info = self.driver.common._create_3par_vlun(self.VOLUME_NAME,
                                                         host, nsp)
        self.assertEqual(expected_info, vlun_info)

        location = ("%(name)s,%(lunid)s,%(host)s" %
                    {'name': self.VOLUME_NAME,
                     'lunid': lun_id,
                     'host': host})
        mock_client.createVLUN.return_value = location
        expected_info = {'volume_name': self.VOLUME_NAME,
                         'lun_id': lun_id,
                         'host_name': host}
        vlun_info = self.driver.common._create_3par_vlun(self.VOLUME_NAME,
                                                         host, None)
        self.assertEqual(expected_info, vlun_info)

    @mock.patch.object(volume_types, 'get_volume_type')
    def test_manage_existing(self, _mock_volume_types):
        mock_client = self.setup_driver()

        _mock_volume_types.return_value = {
            'name': 'gold',
            'extra_specs': {
                'cpg': HP3PAR_CPG,
                'snap_cpg': HP3PAR_CPG_SNAP,
                'vvs_name': self.VVS_NAME,
                'qos': self.QOS,
                'tpvv': True,
                'volume_type': self.volume_type}}
        comment = (
            '{"display_name": "Foo Volume"}')
        new_comment = (
            '{"volume_type_name": "gold",'
            ' "display_name": "Foo Volume",'
            ' "name": "volume-007dbfce-7579-40bc-8f90-a20b3902283e",'
            ' "volume_type_id": "acfa9fa4-54a0-4340-a3d8-bfcf19aea65e",'
            ' "volume_id": "007dbfce-7579-40bc-8f90-a20b3902283e",'
            ' "qos": {},'
            ' "type": "OpenStack"}')
        volume = {'display_name': None,
                  'volume_type': 'gold',
                  'volume_type_id': 'acfa9fa4-54a0-4340-a3d8-bfcf19aea65e',
                  'id': '007dbfce-7579-40bc-8f90-a20b3902283e'}

        mock_client.getVolume.return_value = {'comment': comment}

        unm_matcher = self.driver.common._get_3par_unm_name(self.volume['id'])
        osv_matcher = self.driver.common._get_3par_vol_name(volume['id'])
        existing_ref = {'name': unm_matcher}

        obj = self.driver.manage_existing(volume, existing_ref)

        expected_obj = {'display_name': 'Foo Volume'}
        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getVolume(existing_ref['name']),
            mock.call.modifyVolume(existing_ref['name'],
                                   {'newName': osv_matcher,
                                    'comment': new_comment}),
            mock.call.logout()
        ]

        mock_client.assert_has_calls(expected)
        self.assertEqual(expected_obj, obj)

        volume['display_name'] = 'Test Volume'

        obj = self.driver.manage_existing(volume, existing_ref)

        expected_obj = {'display_name': 'Test Volume'}
        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getVolume(existing_ref['name']),
            mock.call.modifyVolume(existing_ref['name'],
                                   {'newName': osv_matcher,
                                    'comment': new_comment}),
            mock.call.logout()
        ]

        mock_client.assert_has_calls(expected)
        self.assertEqual(expected_obj, obj)

    def test_manage_existing_no_volume_type(self):
        mock_client = self.setup_driver()

        comment = (
            '{"display_name": "Foo Volume"}')
        new_comment = (
            '{"type": "OpenStack",'
            ' "display_name": "Foo Volume",'
            ' "name": "volume-007dbfce-7579-40bc-8f90-a20b3902283e",'
            ' "volume_id": "007dbfce-7579-40bc-8f90-a20b3902283e"}')
        volume = {'display_name': None,
                  'volume_type': None,
                  'id': '007dbfce-7579-40bc-8f90-a20b3902283e'}

        mock_client.getVolume.return_value = {'comment': comment}

        unm_matcher = self.driver.common._get_3par_unm_name(self.volume['id'])
        osv_matcher = self.driver.common._get_3par_vol_name(volume['id'])
        existing_ref = {'name': unm_matcher}

        obj = self.driver.manage_existing(volume, existing_ref)

        expected_obj = {'display_name': 'Foo Volume'}
        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getVolume(existing_ref['name']),
            mock.call.modifyVolume(existing_ref['name'],
                                   {'newName': osv_matcher,
                                    'comment': new_comment}),
            mock.call.logout()
        ]

        mock_client.assert_has_calls(expected)
        self.assertEqual(expected_obj, obj)

        volume['display_name'] = 'Test Volume'

        obj = self.driver.manage_existing(volume, existing_ref)

        expected_obj = {'display_name': 'Test Volume'}
        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getVolume(existing_ref['name']),
            mock.call.modifyVolume(existing_ref['name'],
                                   {'newName': osv_matcher,
                                    'comment': new_comment}),
            mock.call.logout()
        ]

        mock_client.assert_has_calls(expected)
        self.assertEqual(expected_obj, obj)

        mock_client.getVolume.return_value = {}
        volume['display_name'] = None

        obj = self.driver.manage_existing(volume, existing_ref)

        expected_obj = {'display_name': None}
        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getVolume(existing_ref['name']),
            mock.call.modifyVolume(existing_ref['name'],
                                   {'newName': osv_matcher,
                                    'comment': new_comment}),
            mock.call.logout()
        ]

        mock_client.assert_has_calls(expected)
        self.assertEqual(expected_obj, obj)

    def test_manage_existing_invalid_input(self):
        mock_client = self.setup_driver()

        volume = {'display_name': None,
                  'volume_type': None,
                  'id': '007dbfce-7579-40bc-8f90-a20b3902283e'}

        mock_client.getVolume.side_effect = hpexceptions.HTTPNotFound('fake')

        unm_matcher = self.driver.common._get_3par_unm_name(self.volume['id'])
        existing_ref = {'name': unm_matcher}

        self.assertRaises(exception.InvalidInput,
                          self.driver.manage_existing,
                          volume=volume,
                          existing_ref=existing_ref)

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getVolume(existing_ref['name']),
            mock.call.logout()
        ]

        mock_client.assert_has_calls(expected)

    def test_manage_existing_volume_type_exception(self):
        mock_client = self.setup_driver()

        comment = (
            '{"display_name": "Foo Volume"}')
        volume = {'display_name': None,
                  'volume_type': 'gold',
                  'volume_type_id': 'bcfa9fa4-54a0-4340-a3d8-bfcf19aea65e',
                  'id': '007dbfce-7579-40bc-8f90-a20b3902283e'}

        mock_client.getVolume.return_value = {'comment': comment}

        unm_matcher = self.driver.common._get_3par_unm_name(self.volume['id'])
        existing_ref = {'name': unm_matcher}

        self.assertRaises(exception.ManageExistingVolumeTypeMismatch,
                          self.driver.manage_existing,
                          volume=volume,
                          existing_ref=existing_ref)

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getVolume(existing_ref['name']),
            mock.call.logout()
        ]

        mock_client.assert_has_calls(expected)

    def test_manage_existing_get_size(self):
        mock_client = self.setup_driver()
        mock_client.getVolume.return_value = {'sizeMiB': 2048}

        unm_matcher = self.driver.common._get_3par_unm_name(self.volume['id'])
        volume = {}
        existing_ref = {'name': unm_matcher}

        size = self.driver.manage_existing_get_size(volume, existing_ref)

        expected_size = 2
        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getVolume(existing_ref['name']),
            mock.call.logout()
        ]

        mock_client.assert_has_calls(expected, True)
        self.assertEqual(expected_size, size)

    def test_manage_existing_get_size_invalid_reference(self):
        mock_client = self.setup_driver()
        volume = {}
        existing_ref = {'name': self.VOLUME_3PAR_NAME}

        self.assertRaises(exception.ManageExistingInvalidReference,
                          self.driver.manage_existing_get_size,
                          volume=volume,
                          existing_ref=existing_ref)

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.logout()
        ]

        mock_client.assert_has_calls(expected)

        existing_ref = {}

        self.assertRaises(exception.ManageExistingInvalidReference,
                          self.driver.manage_existing_get_size,
                          volume=volume,
                          existing_ref=existing_ref)

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.logout()
        ]

        mock_client.assert_has_calls(expected)

    def test_manage_existing_get_size_invalid_input(self):
        mock_client = self.setup_driver()
        mock_client.getVolume.side_effect = hpexceptions.HTTPNotFound('fake')

        unm_matcher = self.driver.common._get_3par_unm_name(self.volume['id'])
        volume = {}
        existing_ref = {'name': unm_matcher}

        self.assertRaises(exception.InvalidInput,
                          self.driver.manage_existing_get_size,
                          volume=volume,
                          existing_ref=existing_ref)

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getVolume(existing_ref['name']),
            mock.call.logout()
        ]

        mock_client.assert_has_calls(expected)

    def test_unmanage(self):
        mock_client = self.setup_driver()

        self.driver.unmanage(self.volume)

        osv_matcher = self.driver.common._get_3par_vol_name(self.volume['id'])
        unm_matcher = self.driver.common._get_3par_unm_name(self.volume['id'])

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.modifyVolume(osv_matcher, {'newName': unm_matcher}),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)


class TestHP3PARFCDriver(HP3PARBaseDriver, test.TestCase):

    properties = {
        'driver_volume_type': 'fibre_channel',
        'data': {
            'target_lun': 90,
            'target_wwn': ['0987654321234', '123456789000987'],
            'target_discovered': True,
            'initiator_target_map': {'123456789012345':
                                     ['0987654321234', '123456789000987'],
                                     '123456789054321':
                                     ['0987654321234', '123456789000987'],
                                     }}}

    def setup_driver(self, config=None, mock_conf=None):

        self.ctxt = context.get_admin_context()
        mock_client = self.setup_mock_client(
            conf=config,
            m_conf=mock_conf,
            driver=hpfcdriver.HP3PARFCDriver)

        expected = [
            mock.call.setSSHOptions(
                HP3PAR_SAN_IP,
                HP3PAR_USER_NAME,
                HP3PAR_USER_PASS,
                privatekey=HP3PAR_SAN_SSH_PRIVATE,
                port=HP3PAR_SAN_SSH_PORT,
                conn_timeout=HP3PAR_SAN_SSH_CON_TIMEOUT),
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.logout()]
        mock_client.assert_has_calls(expected)
        mock_client.reset_mock()
        return mock_client

    def test_initialize_connection(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        mock_client.getVolume.return_value = {'userCPG': HP3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            hpexceptions.HTTPNotFound('fake'),
            {'name': self.FAKE_HOST,
                'FCPaths': [{'driverVersion': None,
                             'firmwareVersion': None,
                             'hostSpeed': 0,
                             'model': None,
                             'portPos': {'cardPort': 1, 'node': 1,
                                         'slot': 2},
                             'vendor': None,
                             'wwn': self.wwn[0]},
                            {'driverVersion': None,
                             'firmwareVersion': None,
                             'hostSpeed': 0,
                             'model': None,
                             'portPos': {'cardPort': 1, 'node': 0,
                                         'slot': 2},
                             'vendor': None,
                             'wwn': self.wwn[1]}]}]
        mock_client.findHost.return_value = self.FAKE_HOST
        mock_client.getHostVLUNs.return_value = [
            {'active': True,
             'volumeName': self.VOLUME_3PAR_NAME,
             'lun': 90, 'type': 0}]
        location = ("%(volume_name)s,%(lun_id)s,%(host)s,%(nsp)s" %
                    {'volume_name': self.VOLUME_3PAR_NAME,
                     'lun_id': 90,
                     'host': self.FAKE_HOST,
                     'nsp': 'something'})
        mock_client.createVLUN.return_value = location

        result = self.driver.initialize_connection(self.volume, self.connector)

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getVolume(self.VOLUME_3PAR_NAME),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getHost(self.FAKE_HOST),
            mock.ANY,
            mock.call.getHost(self.FAKE_HOST),
            mock.call.createVLUN(
                self.VOLUME_3PAR_NAME,
                auto=True,
                hostname=self.FAKE_HOST),
            mock.call.getHostVLUNs(self.FAKE_HOST),
            mock.call.getPorts(),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

        self.assertDictMatch(result, self.properties)

    def test_terminate_connection(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        effects = [
            [{'active': True, 'volumeName': self.VOLUME_3PAR_NAME,
              'lun': None, 'type': 0}],
            hpexceptions.HTTPNotFound]

        mock_client.getHostVLUNs.side_effect = effects

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getHostVLUNs(self.FAKE_HOST),
            mock.call.deleteVLUN(
                self.VOLUME_3PAR_NAME,
                None,
                self.FAKE_HOST),
            mock.call.deleteHost(self.FAKE_HOST),
            mock.call.getHostVLUNs(self.FAKE_HOST),
            mock.call.getPorts(),
            mock.call.logout()]

        conn_info = self.driver.terminate_connection(self.volume,
                                                     self.connector)
        mock_client.assert_has_calls(expected)
        self.assertIn('data', conn_info)
        self.assertIn('initiator_target_map', conn_info['data'])
        mock_client.reset_mock()

        mock_client.getHostVLUNs.side_effect = effects

        # mock some deleteHost exceptions that are handled
        delete_with_vlun = hpexceptions.HTTPConflict(
            error={'message': "has exported VLUN"})
        delete_with_hostset = hpexceptions.HTTPConflict(
            error={'message': "host is a member of a set"})
        mock_client.deleteHost = mock.Mock(
            side_effect=[delete_with_vlun, delete_with_hostset])

        conn_info = self.driver.terminate_connection(self.volume,
                                                     self.connector)
        mock_client.assert_has_calls(expected)
        mock_client.reset_mock()
        mock_client.getHostVLUNs.side_effect = effects

        conn_info = self.driver.terminate_connection(self.volume,
                                                     self.connector)
        mock_client.assert_has_calls(expected)

    def test_terminate_connection_more_vols(self):
        mock_client = self.setup_driver()
        # mock more than one vlun on the host (don't even try to remove host)
        mock_client.getHostVLUNs.return_value = \
            [
                {'active': True,
                 'volumeName': self.VOLUME_3PAR_NAME,
                 'lun': None, 'type': 0},
                {'active': True,
                 'volumeName': 'there-is-another-volume',
                 'lun': None, 'type': 0},
            ]

        expect_less = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getHostVLUNs(self.FAKE_HOST),
            mock.call.deleteVLUN(
                self.VOLUME_3PAR_NAME,
                None,
                self.FAKE_HOST),
            mock.call.getHostVLUNs(self.FAKE_HOST),
            mock.call.logout()]

        conn_info = self.driver.terminate_connection(self.volume,
                                                     self.connector)
        mock_client.assert_has_calls(expect_less)
        self.assertNotIn('initiator_target_map', conn_info['data'])

    def test_get_volume_stats(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        mock_client.getCPG.return_value = self.cpgs[0]
        mock_client.getStorageSystemInfo.return_value = {'serialNumber':
                                                         '1234'}
        stats = self.driver.get_volume_stats(True)
        self.assertEqual(stats['storage_protocol'], 'FC')
        self.assertEqual(stats['total_capacity_gb'], 'infinite')
        self.assertEqual(stats['free_capacity_gb'], 'infinite')

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getStorageSystemInfo(),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)
        stats = self.driver.get_volume_stats(True)
        self.assertEqual(stats['storage_protocol'], 'FC')
        self.assertEqual(stats['total_capacity_gb'], 'infinite')
        self.assertEqual(stats['free_capacity_gb'], 'infinite')

        cpg2 = self.cpgs[0].copy()
        cpg2.update({'SDGrowth': {'limitMiB': 8192}})
        mock_client.getCPG.return_value = cpg2

        const = 0.0009765625
        stats = self.driver.get_volume_stats(True)
        self.assertEqual(stats['storage_protocol'], 'FC')
        total_capacity_gb = 8192 * const
        self.assertEqual(stats['total_capacity_gb'], total_capacity_gb)
        free_capacity_gb = int(
            (8192 - self.cpgs[0]['UsrUsage']['usedMiB']) * const)
        self.assertEqual(stats['free_capacity_gb'], free_capacity_gb)
        self.driver.common.client.deleteCPG(HP3PAR_CPG)
        self.driver.common.client.createCPG(HP3PAR_CPG, {})

    def test_create_host(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        mock_client.getVolume.return_value = {'userCPG': HP3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            hpexceptions.HTTPNotFound('fake'),
            {'name': self.FAKE_HOST,
                'FCPaths': [{'driverVersion': None,
                             'firmwareVersion': None,
                             'hostSpeed': 0,
                             'model': None,
                             'portPos': {'cardPort': 1, 'node': 1,
                                         'slot': 2},
                             'vendor': None,
                             'wwn': self.wwn[0]},
                            {'driverVersion': None,
                             'firmwareVersion': None,
                             'hostSpeed': 0,
                             'model': None,
                             'portPos': {'cardPort': 1, 'node': 0,
                                         'slot': 2},
                             'vendor': None,
                             'wwn': self.wwn[1]}]}]
        mock_client.findHost.return_value = None
        mock_client.getVLUN.return_value = {'lun': 186}

        host = self.driver._create_host(self.volume, self.connector)
        expected = [
            mock.call.getVolume('osv-0DM4qZEVSKON-DXN-NwVpw'),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getHost(self.FAKE_HOST),
            mock.call.findHost(wwn='123456789012345'),
            mock.call.findHost(wwn='123456789054321'),
            mock.call.createHost(
                self.FAKE_HOST,
                FCWwns=['123456789012345', '123456789054321'],
                optional={'domain': None, 'persona': 1}),
            mock.call.getHost(self.FAKE_HOST)]

        mock_client.assert_has_calls(expected)

        self.assertEqual(host['name'], self.FAKE_HOST)

    def test_create_invalid_host(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        mock_client.getVolume.return_value = {'userCPG': HP3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            hpexceptions.HTTPNotFound('Host not found.'), {
                'name': 'fakehost.foo',
                'FCPaths': [{'wwn': '123456789012345'}, {
                    'wwn': '123456789054321'}]}]
        mock_client.findHost.return_value = 'fakehost.foo'

        host = self.driver._create_host(self.volume, self.connector)

        expected = [
            mock.call.getVolume('osv-0DM4qZEVSKON-DXN-NwVpw'),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getHost('fakehost'),
            mock.call.findHost(wwn='123456789012345'),
            mock.call.getHost('fakehost.foo')]

        mock_client.assert_has_calls(expected)

        self.assertEqual(host['name'], 'fakehost.foo')

    def test_create_modify_host(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        mock_client.getVolume.return_value = {'userCPG': HP3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [{
            'name': self.FAKE_HOST, 'FCPaths': []},
            {'name': self.FAKE_HOST,
                'FCPaths': [{'wwn': '123456789012345'}, {
                    'wwn': '123456789054321'}]}]

        host = self.driver._create_host(self.volume, self.connector)
        expected = [
            mock.call.getVolume('osv-0DM4qZEVSKON-DXN-NwVpw'),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getHost('fakehost'),
            mock.call.modifyHost(
                'fakehost', {
                    'FCWWNs': ['123456789012345', '123456789054321'],
                    'pathOperation': 1}),
            mock.call.getHost('fakehost')]

        mock_client.assert_has_calls(expected)

        self.assertEqual(host['name'], self.FAKE_HOST)
        self.assertEqual(len(host['FCPaths']), 2)

    def test_modify_host_with_new_wwn(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        mock_client.getVolume.return_value = {'userCPG': HP3PAR_CPG}
        mock_client.getCPG.return_value = {}
        getHost_ret1 = {
            'name': self.FAKE_HOST,
            'FCPaths': [{'wwn': '123456789054321'}]}
        getHost_ret2 = {
            'name': self.FAKE_HOST,
            'FCPaths': [{'wwn': '123456789012345'},
                        {'wwn': '123456789054321'}]}
        mock_client.getHost.side_effect = [getHost_ret1, getHost_ret2]

        host = self.driver._create_host(self.volume, self.connector)

        expected = [
            mock.call.getVolume('osv-0DM4qZEVSKON-DXN-NwVpw'),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getHost('fakehost'),
            mock.call.modifyHost(
                'fakehost', {
                    'FCWWNs': ['123456789012345'], 'pathOperation': 1}),
            mock.call.getHost('fakehost')]

        mock_client.assert_has_calls(expected)

        self.assertEqual(host['name'], self.FAKE_HOST)
        self.assertEqual(len(host['FCPaths']), 2)

    def test_modify_host_with_unknown_wwn_and_new_wwn(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        mock_client.getVolume.return_value = {'userCPG': HP3PAR_CPG}
        mock_client.getCPG.return_value = {}
        getHost_ret1 = {
            'name': self.FAKE_HOST,
            'FCPaths': [{'wwn': '123456789054321'},
                        {'wwn': 'xxxxxxxxxxxxxxx'}]}
        getHost_ret2 = {
            'name': self.FAKE_HOST,
            'FCPaths': [{'wwn': '123456789012345'},
                        {'wwn': '123456789054321'},
                        {'wwn': 'xxxxxxxxxxxxxxx'}]}
        mock_client.getHost.side_effect = [getHost_ret1, getHost_ret2]

        host = self.driver._create_host(self.volume, self.connector)

        expected = [
            mock.call.getVolume('osv-0DM4qZEVSKON-DXN-NwVpw'),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getHost('fakehost'),
            mock.call.modifyHost(
                'fakehost', {
                    'FCWWNs': ['123456789012345'], 'pathOperation': 1}),
            mock.call.getHost('fakehost')]

        mock_client.assert_has_calls(expected)

        self.assertEqual(host['name'], self.FAKE_HOST)
        self.assertEqual(len(host['FCPaths']), 3)


class TestHP3PARISCSIDriver(HP3PARBaseDriver, test.TestCase):

    TARGET_IQN = 'iqn.2000-05.com.3pardata:21810002ac00383d'
    TARGET_LUN = 186

    properties = {
        'driver_volume_type': 'iscsi',
        'data':
        {'target_discovered': True,
            'target_iqn': TARGET_IQN,
            'target_lun': TARGET_LUN,
            'target_portal': '1.1.1.2:1234'}}

    def setup_driver(self, config=None, mock_conf=None):

        self.ctxt = context.get_admin_context()

        mock_client = self.setup_mock_client(
            conf=config,
            m_conf=mock_conf,
            driver=hpdriver.HP3PARISCSIDriver)

        expected = [
            mock.call.setSSHOptions(
                HP3PAR_SAN_IP,
                HP3PAR_USER_NAME,
                HP3PAR_USER_PASS,
                privatekey=HP3PAR_SAN_SSH_PRIVATE,
                port=HP3PAR_SAN_SSH_PORT,
                conn_timeout=HP3PAR_SAN_SSH_CON_TIMEOUT),
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.logout(),
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getPorts(),
            mock.call.logout()]
        mock_client.assert_has_calls(expected)
        mock_client.reset_mock()

        return mock_client

    def test_initialize_connection(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        mock_client.getVolume.return_value = {'userCPG': HP3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            hpexceptions.HTTPNotFound('fake'),
            {'name': self.FAKE_HOST}]
        mock_client.findHost.return_value = self.FAKE_HOST
        mock_client.getHostVLUNs.return_value = [
            {'active': True,
             'volumeName': self.VOLUME_3PAR_NAME,
             'lun': self.TARGET_LUN, 'type': 0}]
        location = ("%(volume_name)s,%(lun_id)s,%(host)s,%(nsp)s" %
                    {'volume_name': self.VOLUME_3PAR_NAME,
                     'lun_id': self.TARGET_LUN,
                     'host': self.FAKE_HOST,
                     'nsp': 'something'})
        mock_client.createVLUN.return_value = location

        result = self.driver.initialize_connection(self.volume, self.connector)

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getVolume(self.VOLUME_3PAR_NAME),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getHost(self.FAKE_HOST),
            mock.call.findHost(iqn='iqn.1993-08.org.debian:01:222'),
            mock.call.getHost(self.FAKE_HOST),
            mock.call.createVLUN(
                self.VOLUME_3PAR_NAME,
                auto=True,
                hostname='fakehost',
                portPos={'node': 8, 'slot': 1, 'cardPort': 1}),
            mock.call.getHostVLUNs(self.FAKE_HOST),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

        self.assertDictMatch(result, self.properties)

    def test_get_volume_stats(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        mock_client.getCPG.return_value = self.cpgs[0]
        mock_client.getStorageSystemInfo.return_value = {'serialNumber':
                                                         '1234'}
        stats = self.driver.get_volume_stats(True)
        self.assertEqual(stats['storage_protocol'], 'iSCSI')
        self.assertEqual(stats['total_capacity_gb'], 'infinite')
        self.assertEqual(stats['free_capacity_gb'], 'infinite')

        expected = [
            mock.call.login(HP3PAR_USER_NAME, HP3PAR_USER_PASS),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getStorageSystemInfo(),
            mock.call.logout()]

        mock_client.assert_has_calls(expected)

        self.assertEqual(stats['storage_protocol'], 'iSCSI')
        self.assertEqual(stats['total_capacity_gb'], 'infinite')
        self.assertEqual(stats['free_capacity_gb'], 'infinite')

        cpg2 = self.cpgs[0].copy()
        cpg2.update({'SDGrowth': {'limitMiB': 8192}})
        mock_client.getCPG.return_value = cpg2

        const = 0.0009765625
        stats = self.driver.get_volume_stats(True)
        self.assertEqual(stats['storage_protocol'], 'iSCSI')
        total_capacity_gb = 8192 * const
        self.assertEqual(stats['total_capacity_gb'], total_capacity_gb)
        free_capacity_gb = int(
            (8192 - self.cpgs[0]['UsrUsage']['usedMiB']) * const)
        self.assertEqual(stats['free_capacity_gb'], free_capacity_gb)

    def test_create_host(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        mock_client.getVolume.return_value = {'userCPG': HP3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            hpexceptions.HTTPNotFound('fake'),
            {'name': self.FAKE_HOST}]
        mock_client.findHost.return_value = None
        mock_client.getVLUN.return_value = {'lun': self.TARGET_LUN}

        host = self.driver._create_host(self.volume, self.connector)
        expected = [
            mock.call.getVolume('osv-0DM4qZEVSKON-DXN-NwVpw'),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getHost(self.FAKE_HOST),
            mock.call.findHost(iqn='iqn.1993-08.org.debian:01:222'),
            mock.call.createHost(
                self.FAKE_HOST,
                optional={'domain': None, 'persona': 1},
                iscsiNames=['iqn.1993-08.org.debian:01:222']),
            mock.call.getHost(self.FAKE_HOST)]

        mock_client.assert_has_calls(expected)

        self.assertEqual(host['name'], self.FAKE_HOST)

    def test_create_invalid_host(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        mock_client.getVolume.return_value = {'userCPG': HP3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            hpexceptions.HTTPNotFound('Host not found.'),
            {'name': 'fakehost.foo'}]
        mock_client.findHost.return_value = 'fakehost.foo'

        host = self.driver._create_host(self.volume, self.connector)

        expected = [
            mock.call.getVolume('osv-0DM4qZEVSKON-DXN-NwVpw'),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getHost(self.FAKE_HOST),
            mock.call.findHost(iqn='iqn.1993-08.org.debian:01:222'),
            mock.call.getHost('fakehost.foo')]

        mock_client.assert_has_calls(expected)

        self.assertEqual(host['name'], 'fakehost.foo')

    def test_create_modify_host(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        mock_client.getVolume.return_value = {'userCPG': HP3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            {'name': self.FAKE_HOST, 'FCPaths': []},
            {'name': self.FAKE_HOST,
             'FCPaths': [{'wwn': '123456789012345'},
                         {'wwn': '123456789054321'}]}]

        host = self.driver._create_host(self.volume, self.connector)

        expected = [
            mock.call.getVolume('osv-0DM4qZEVSKON-DXN-NwVpw'),
            mock.call.getCPG(HP3PAR_CPG),
            mock.call.getHost(self.FAKE_HOST),
            mock.call.modifyHost(
                self.FAKE_HOST,
                {'pathOperation': 1,
                    'iSCSINames': ['iqn.1993-08.org.debian:01:222']}),
            mock.call.getHost(self.FAKE_HOST)]

        mock_client.assert_has_calls(expected)

        self.assertEqual(host['name'], self.FAKE_HOST)
        self.assertEqual(len(host['FCPaths']), 2)

    def test_get_least_used_nsp_for_host_single(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        mock_client.getPorts.return_value = PORTS_RET
        mock_client.getVLUNs.return_value = VLUNS1_RET

        #Setup a single ISCSI IP
        iscsi_ips = ["10.10.220.253"]
        self.driver.configuration.hp3par_iscsi_ips = iscsi_ips

        self.driver.initialize_iscsi_ports()

        nsp = self.driver._get_least_used_nsp_for_host('newhost')
        self.assertEqual(nsp, "1:8:1")

    def test_get_least_used_nsp_for_host_new(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        mock_client.getPorts.return_value = PORTS_RET
        mock_client.getVLUNs.return_value = VLUNS1_RET

        #Setup two ISCSI IPs
        iscsi_ips = ["10.10.220.252", "10.10.220.253"]
        self.driver.configuration.hp3par_iscsi_ips = iscsi_ips

        self.driver.initialize_iscsi_ports()

        # Host 'newhost' does not yet have any iscsi paths,
        # so the 'least used' is returned
        nsp = self.driver._get_least_used_nsp_for_host('newhost')
        self.assertEqual(nsp, "1:8:2")

    def test_get_least_used_nsp_for_host_reuse(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        mock_client.getPorts.return_value = PORTS_RET
        mock_client.getVLUNs.return_value = VLUNS1_RET

        #Setup two ISCSI IPs
        iscsi_ips = ["10.10.220.252", "10.10.220.253"]
        self.driver.configuration.hp3par_iscsi_ips = iscsi_ips

        self.driver.initialize_iscsi_ports()

        # hosts 'foo' and 'bar' already have active iscsi paths
        # the same one should be used
        nsp = self.driver._get_least_used_nsp_for_host('foo')
        self.assertEqual(nsp, "1:8:2")

        nsp = self.driver._get_least_used_nsp_for_host('bar')
        self.assertEqual(nsp, "1:8:1")

    def test_get_least_used_nps_for_host_fc(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()

        mock_client.getPorts.return_value = PORTS1_RET
        mock_client.getVLUNs.return_value = VLUNS5_RET

        #Setup two ISCSI IPs
        iscsi_ips = ["10.10.220.252", "10.10.220.253"]
        self.driver.configuration.hp3par_iscsi_ips = iscsi_ips

        self.driver.initialize_iscsi_ports()

        nsp = self.driver._get_least_used_nsp_for_host('newhost')
        self.assertNotEqual(nsp, "0:6:3")
        self.assertEqual(nsp, "1:8:1")

    def test_invalid_iscsi_ip(self):
        config = self.setup_configuration()
        config.hp3par_iscsi_ips = ['10.10.220.250', '10.10.220.251']
        config.iscsi_ip_address = '10.10.10.10'
        mock_conf = {
            'getPorts.return_value': {
                'members': [
                    {'portPos': {'node': 1, 'slot': 8, 'cardPort': 2},
                     'protocol': 2,
                     'IPAddr': '10.10.220.252',
                     'linkState': 4,
                     'device': [],
                     'iSCSIName': self.TARGET_IQN,
                     'mode': 2,
                     'HWAddr': '2C27D75375D2',
                     'type': 8},
                    {'portPos': {'node': 1, 'slot': 8, 'cardPort': 1},
                     'protocol': 2,
                     'IPAddr': '10.10.220.253',
                     'linkState': 4,
                     'device': [],
                     'iSCSIName': self.TARGET_IQN,
                     'mode': 2,
                     'HWAddr': '2C27D75375D6',
                     'type': 8}]}}

        # no valid ip addr should be configured.
        self.assertRaises(exception.InvalidInput,
                          self.setup_driver,
                          config=config,
                          mock_conf=mock_conf)

    def test_get_least_used_nsp(self):
        # setup_mock_client drive with default configuration
        # and return the mock HTTP 3PAR client
        mock_client = self.setup_driver()
        ports = [
            {'portPos': {'node': 1, 'slot': 8, 'cardPort': 2}, 'active': True},
            {'portPos': {'node': 1, 'slot': 8, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 1, 'slot': 8, 'cardPort': 2}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 2}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True}]
        mock_client.getVLUNs.return_value = {'members': ports}

        # in use count
        vluns = self.driver.common.client.getVLUNs()
        nsp = self.driver._get_least_used_nsp(vluns['members'],
                                              ['0:2:1', '1:8:1'])
        self.assertEqual(nsp, '1:8:1')

        ports = [
            {'portPos': {'node': 1, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 1, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 1, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 1, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True}]

        mock_client.getVLUNs.return_value = {'members': ports}

        # in use count
        vluns = self.driver.common.client.getVLUNs()
        nsp = self.driver._get_least_used_nsp(vluns['members'],
                                              ['0:2:1', '1:2:1'])
        self.assertEqual(nsp, '1:2:1')

        ports = [
            {'portPos': {'node': 1, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 1, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 1, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 1, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True},
            {'portPos': {'node': 0, 'slot': 2, 'cardPort': 1}, 'active': True}]

        mock_client.getVLUNs.return_value = {'members': ports}

        # in use count
        vluns = self.driver.common.client.getVLUNs()
        nsp = self.driver._get_least_used_nsp(vluns['members'],
                                              ['1:1:1', '1:2:1'])
        self.assertEqual(nsp, '1:1:1')

VLUNS5_RET = ({'members':
               [{'portPos': {'node': 0, 'slot': 8, 'cardPort': 2},
                 'active': True},
                {'portPos': {'node': 1, 'slot': 8, 'cardPort': 1},
                 'active': True}]})

PORTS_RET = ({'members':
              [{'portPos': {'node': 1, 'slot': 8, 'cardPort': 2},
                'protocol': 2,
                'IPAddr': '10.10.220.252',
                'linkState': 4,
                'device': [],
                'iSCSIName': 'iqn.2000-05.com.3pardata:21820002ac00383d',
                'mode': 2,
                'HWAddr': '2C27D75375D2',
                'type': 8},
               {'portPos': {'node': 1, 'slot': 8, 'cardPort': 1},
                'protocol': 2,
                'IPAddr': '10.10.220.253',
                'linkState': 4,
                'device': [],
                'iSCSIName': 'iqn.2000-05.com.3pardata:21810002ac00383d',
                'mode': 2,
                'HWAddr': '2C27D75375D6',
                'type': 8}]})

VLUNS1_RET = ({'members':
               [{'portPos': {'node': 1, 'slot': 8, 'cardPort': 2},
                 'hostname': 'foo', 'active': True},
                {'portPos': {'node': 1, 'slot': 8, 'cardPort': 1},
                 'hostname': 'bar', 'active': True},
                {'portPos': {'node': 1, 'slot': 8, 'cardPort': 1},
                 'hostname': 'bar', 'active': True},
                {'portPos': {'node': 1, 'slot': 8, 'cardPort': 1},
                 'hostname': 'bar', 'active': True}]})

PORTS1_RET = ({'members':
               [{'portPos': {'node': 0, 'slot': 8, 'cardPort': 2},
                 'protocol': 2,
                 'IPAddr': '10.10.120.252',
                 'linkState': 4,
                 'device': [],
                 'iSCSIName': 'iqn.2000-05.com.3pardata:21820002ac00383d',
                 'mode': 2,
                 'HWAddr': '2C27D75375D2',
                 'type': 8},
                {'portPos': {'node': 1, 'slot': 8, 'cardPort': 1},
                 'protocol': 2,
                 'IPAddr': '10.10.220.253',
                 'linkState': 4,
                 'device': [],
                 'iSCSIName': 'iqn.2000-05.com.3pardata:21810002ac00383d',
                 'mode': 2,
                 'HWAddr': '2C27D75375D6',
                 'type': 8},
                {'portWWN': '20210002AC00383D',
                 'protocol': 1,
                 'linkState': 4,
                 'mode': 2,
                 'device': ['cage2'],
                 'nodeWWN': '20210002AC00383D',
                 'type': 2,
                 'portPos': {'node': 0, 'slot': 6, 'cardPort': 3}}]})
