
from mock import MagicMock, patch
from collections import OrderedDict
import charmhelpers.contrib.openstack.templating as templating

templating.OSConfigRenderer = MagicMock()

import neutron_calico_utils as nutils

from test_utils import (
    CharmTestCase,
)
import charmhelpers
import charmhelpers.core.hookenv as hookenv


TO_PATCH = [
    'os_release',
    'neutron_plugin_attribute',
]

head_pkg = 'linux-headers-3.15.0-5-generic'


def _mock_npa(plugin, attr, net_manager=None):
    plugins = {
        'ovs': {
            'config': '/etc/neutron/plugins/ml2/ml2_conf.ini',
            'driver': 'neutron.plugins.ml2.plugin.Ml2Plugin',
            'contexts': [],
            'services': ['neutron-plugin-openvswitch-agent'],
            'packages': [[head_pkg], ['neutron-plugin-openvswitch-agent']],
            'server_packages': ['neutron-server',
                                'neutron-plugin-ml2'],
            'server_services': ['neutron-server']
        },
        'Calico': {
            'config': '/etc/neutron/plugins/ml2/ml2_conf.ini',
            'driver': 'neutron.plugins.ml2.plugin.Ml2Plugin',
            'contexts': [],
            'services': ['calico-compute', 'bird', 'neutron-dhcp-agent'],
            'packages': [[head_pkg], ['calico-compute',
                                      'bird',
                                      'neutron-dhcp-agent']],
            'server_packages': ['neutron-server',
                                'calico-control'],
            'server_services': ['neutron-server']
        }
    }
    return plugins[plugin][attr]


class TestNeutronCalicoUtils(CharmTestCase):

    def setUp(self):
        super(TestNeutronCalicoUtils, self).setUp(nutils, TO_PATCH)
        self.neutron_plugin_attribute.side_effect = _mock_npa

    def tearDown(self):
        # Reset cached cache
        hookenv.cache = {}

    @patch.object(charmhelpers.contrib.openstack.neutron, 'os_release')
    @patch.object(charmhelpers.contrib.openstack.neutron, 'headers_package')
    def test_determine_packages(self, _head_pkgs, _os_rel):
        _os_rel.return_value = 'trusty'
        _head_pkgs.return_value = head_pkg
        pkg_list = nutils.determine_packages()
        expect = [['calico-compute', 'bird', 'neutron-dhcp-agent'], [head_pkg]]
        self.assertItemsEqual(pkg_list, expect)

    def test_register_configs(self):
        class _mock_OSConfigRenderer():
            def __init__(self, templates_dir=None, openstack_release=None):
                self.configs = []
                self.ctxts = []

            def register(self, config, ctxt):
                self.configs.append(config)
                self.ctxts.append(ctxt)

        self.os_release.return_value = 'trusty'
        templating.OSConfigRenderer.side_effect = _mock_OSConfigRenderer
        _regconfs = nutils.register_configs()
        confs = ['/etc/neutron/neutron.conf',
                 '/etc/bird/bird.conf',
                 '/etc/neutron/dhcp_agent.ini',
                 '/etc/calico/felix.cfg']
        self.assertItemsEqual(_regconfs.configs, confs)

    def test_resource_map(self):
        _map = nutils.resource_map()
        confs = [nutils.NEUTRON_CONF]
        [self.assertIn(q_conf, _map.keys()) for q_conf in confs]

    def test_restart_map(self):
        _restart_map = nutils.restart_map()
        expect = OrderedDict([
            (nutils.NEUTRON_CONF, ['calico-compute',
                                   'neutron-dhcp-agent',
                                   'nova-api-metadata']),
            (nutils.BIRD_CONF, ['bird']),
            (nutils.DHCP_CONF, ['neutron-dhcp-agent']),
            (nutils.FELIX_CONF, ['calico-compute']),
        ])
        print _restart_map
        self.assertTrue(len(expect) == len(_restart_map))
        for item in _restart_map:
            self.assertTrue(item in _restart_map)
            self.assertEqual(expect[item], _restart_map[item])
