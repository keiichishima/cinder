# Copyright 2014 IIJ Innovation Institute Inc. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#     * Redistributions of source code must retain the above
#       copyright notice, this list of conditions and the following
#       disclaimer.
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials
#       provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY IIJ INNOVATION INSTITUTE INC. ``AS
# IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL IIJ
# INNOVATION INSTITUTE INC. OR CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE
# GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import errno
import os
import re

from oslo.config import cfg

from cinder.brick.remotefs import remotefs
from cinder import exception
from cinder.image import image_utils
from cinder.openstack.common import log as logging
from cinder.openstack.common import processutils as putils
from cinder import units
from cinder import utils
from cinder.volume import driver
from cinder.volume.drivers import nfs

VERSION = '0.0.1'

LOG = logging.getLogger(__name__)

volume_opts = [
    cfg.StrOpt('ukai_shares_config',
               default='/etc/cinder/ukai_shares',
               help='File with the list of available ukai shares'),
    cfg.StrOpt('ukai_mount_point_base',
               default='$state_path/mnt',
               help=('Base dir containing mount points for ukai shares.')),
    cfg.StrOpt('ukai_mount_options',
               default=None,
               help='Mount options passed to the ukai client.'),
]

CONF = cfg.CONF
CONF.register_opts(volume_opts)

class UkaiDriver(nfs.RemoteFsDriver):
    '''UKAI based cinder driver.  '''

    driver_volume_type = 'ukai'
    driver_prefix = 'ukai'
    volume_backend_name = 'UKAI'
    VERSION = VERSION

    def __init__(self, execute=putils.execute, *args, **kwargs):
        self._remotefsclient = None
        super(UkaiDriver, self).__init__(*args, **kwargs)
        self.configuration.append_config_values(volume_opts)
        root_helper = utils.get_root_helper()
        # base bound to instance is used in RemoteFsConnector.
        self.base = getattr(self.configuration,
                            'ukai_mount_point_base',
                            CONF.ukai_mount_point_base)
        opts = getattr(self.configuration,
                       'ukai_mount_options',
                       CONF.ukai_mount_options)
        self._remotefsclient = remotefs.RemoteFsClient(
            'ukai', root_helper, execute=execute,
            nfs_mount_point_base=self.base,
            nfs_mount_options=opts)

    def set_execute(self, execute):
        super(UkaiDriver, self).set_execute(execute)
        if self._remotefsclient:
            self._remotefsclient.set_execute(execute)

    def do_setup(self, context):
        """Any initialization the volume driver does while starting."""
        super(UkaiDriver, self).do_setup(context)

        config = self.configuration.ukai_shares_config
        if not config:
            msg = (_("There's no UKAI config file configured (%s)") %
                   'ukai_shares_config')
            LOG.warn(msg)
            raise exception.UkaiException(msg)
        if not os.path.exists(config):
            msg = (_("UKAI config file at %(config)s doesn't exist") %
                   {'config': config})
            LOG.warn(msg)
            raise exception.UkaiException(msg)

        self.shares = {}  # address : options

        # Check if mount.nfs is installed
        try:
            self._execute('ukai', check_exit_code=False, run_as_root=True)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                raise exception.UkaiException('ukai is not installed')
            else:
                raise exc

    def _ensure_share_mounted(self, nfs_share):
        mnt_flags = []
        if self.shares.get(ukai_share) is not None:
            mnt_flags = self.shares[ukai_share].split()
        self._remotefsclient.mount(ukai_share, mnt_flags)

    def _find_share(self, volume_size_in_gib):
        """Choose NFS share among available ones for given volume size.

        For instances with more than one share that meets the criteria, the
        share with the least "allocated" space will be selected.

        :param volume_size_in_gib: int size in GB
        """

        if not self._mounted_shares:
            raise exception.UkaiNoSharesMounted()

        target_share = None
        target_share_reserved = 0

        for nfs_share in self._mounted_shares:
            if not self._is_share_eligible(ukai_share, volume_size_in_gib):
                continue
            total_size, total_available, total_allocated = \
                self._get_capacity_info(ukai_share)
            if target_share is not None:
                if target_share_reserved > total_allocated:
                    target_share = ukai_share
                    target_share_reserved = total_allocated
            else:
                target_share = ukai_share
                target_share_reserved = total_allocated

        if target_share is None:
            raise exception.UkaiNoSuitableShareFound(
                volume_size=volume_size_in_gib)

        LOG.debug(_('Selected %s as target UKAI share.'), target_share)

        return target_share

    def _is_share_eligible(self, nfs_share, volume_size_in_gib):
        return True

    '''
    def _is_share_eligible(self, nfs_share, volume_size_in_gib):
        """Verifies NFS share is eligible to host volume with given size.

        First validation step: ratio of actual space (used_space / total_space)
        is less than 'nfs_used_ratio'. Second validation step: apparent space
        allocated (differs from actual space used when using sparse files)
        and compares the apparent available
        space (total_available * nfs_oversub_ratio) to ensure enough space is
        available for the new volume.

        :param nfs_share: nfs share
        :param volume_size_in_gib: int size in GB
        """

        used_ratio = self.configuration.nfs_used_ratio
        oversub_ratio = self.configuration.nfs_oversub_ratio
        requested_volume_size = volume_size_in_gib * units.GiB

        total_size, total_available, total_allocated = \
            self._get_capacity_info(nfs_share)
        apparent_size = max(0, total_size * oversub_ratio)
        apparent_available = max(0, apparent_size - total_allocated)
        used = (total_size - total_available) / total_size
        if used > used_ratio:
            # NOTE(morganfainberg): We check the used_ratio first since
            # with oversubscription it is possible to not have the actual
            # available space but be within our oversubscription limit
            # therefore allowing this share to still be selected as a valid
            # target.
            LOG.debug(_('%s is above nfs_used_ratio'), nfs_share)
            return False
        if apparent_available <= requested_volume_size:
            LOG.debug(_('%s is above nfs_oversub_ratio'), nfs_share)
            return False
        if total_allocated / total_size >= oversub_ratio:
            LOG.debug(_('%s reserved space is above nfs_oversub_ratio'),
                      nfs_share)
            return False
        return True
    '''

    def _get_mount_point_for_share(self, ukai_share):
        """Needed by parent class."""
        return self._remotefsclient.get_mount_point(ukai_share)

    def _get_capacity_info(self, ukai_share):
        return 1000000000000, 1000000000000, 0

    '''
    def _get_capacity_info(self, ukai_share):
        """Calculate available space on the UKAI share.

        :param nfs_share: example 172.18.194.100:/var/nfs
        """

        mount_point = self._get_mount_point_for_share(ukai_share)

        df, _ = self._execute('stat', '-f', '-c', '%S %b %a', mount_point,
                              run_as_root=True)
        block_size, blocks_total, blocks_avail = map(float, df.split())
        total_available = block_size * blocks_avail
        total_size = block_size * blocks_total

        du, _ = self._execute('du', '-sb', '--apparent-size', '--exclude',
                              '*snapshot*', mount_point, run_as_root=True)
        total_allocated = float(du.split()[0])
        return total_size, total_available, total_allocated
    '''

    def _get_mount_point_base(self):
        return self.base
