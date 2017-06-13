import os
import sys
import unittest
import time
import json
import requests
import threading
from random import randint
from threading import Timer
from nose.tools import *
from nose.twistedtools import reactor, deferred
from twisted.internet import defer
from CordTestConfig import setup_module
from CordTestUtils import log_test
from VolthaCtrl import VolthaCtrl
from CordTestUtils import log_test, get_controller
from portmaps import g_subscriber_port_map
from OltConfig import *
from EapTLS import TLSAuthTest
from OnosCtrl import OnosCtrl
from CordLogger import CordLogger
from scapy.all import *
from scapy_ssl_tls.ssl_tls import *
from scapy_ssl_tls.ssl_tls_crypto import *
from CordTestServer import cord_test_onos_restart, cord_test_shell, cord_test_radius_restart
from CordContainer import Onos

class voltha_exchange(unittest.TestCase):

    OLT_TYPE = 'tibit_olt'
    OLT_MAC = '00:0c:e2:31:12:00'
    VOLTHA_HOST = 'localhost'
    VOLTHA_REST_PORT = 8881
    voltha = None
    success = True
    apps = ('org.opencord.aaa', 'org.onosproject.dhcp')
    olt_apps = () #'org.opencord.cordmcast')
    vtn_app = 'org.opencord.vtn'
    table_app = 'org.ciena.cordigmp'
    test_path = os.path.dirname(os.path.realpath(__file__))
    table_app_file = os.path.join(test_path, '..', 'apps/ciena-cordigmp-multitable-2.0-SNAPSHOT.oar')
    app_file = os.path.join(test_path, '..', 'apps/ciena-cordigmp-2.0-SNAPSHOT.oar')
    olt_app_file = os.path.join(test_path, '..', 'apps/olt-app-1.2-SNAPSHOT.oar')
    olt_app_name = 'org.onosproject.olt'
    #onos_config_path = os.path.join(test_path, '..', 'setup/onos-config')
    olt_conf_file = os.getenv('OLT_CONFIG_FILE', os.path.join(test_path, '..', 'setup/olt_config.json'))
    onos_restartable = bool(int(os.getenv('ONOS_RESTART', 0)))
    VOLTHA_ENABLED  = True
    INTF_TX_DEFAULT = 'veth2'
    INTF_RX_DEFAULT = 'veth0'
    INTF_2_RX_DEFAULT = 'veth6'
    TESTCASE_TIMEOUT = 300
#    VOLTHA_CONFIG_FAKE = True
    VOLTHA_CONFIG_FAKE = False
    VOLTHA_UPLINK_VLAN_MAP = { 'of:0000000000000001' : '222' }
    VOLTHA_ONU_UNI_PORT = 'veth0'

    CLIENT_CERT = """-----BEGIN CERTIFICATE-----
MIICuDCCAiGgAwIBAgIBAjANBgkqhkiG9w0BAQUFADCBizELMAkGA1UEBhMCVVMx
CzAJBgNVBAgTAkNBMRIwEAYDVQQHEwlTb21ld2hlcmUxEzARBgNVBAoTCkNpZW5h
IEluYy4xHjAcBgkqhkiG9w0BCQEWD2FkbWluQGNpZW5hLmNvbTEmMCQGA1UEAxMd
RXhhbXBsZSBDZXJ0aWZpY2F0ZSBBdXRob3JpdHkwHhcNMTYwNjA2MjExMjI3WhcN
MTcwNjAxMjExMjI3WjBnMQswCQYDVQQGEwJVUzELMAkGA1UECBMCQ0ExEzARBgNV
BAoTCkNpZW5hIEluYy4xFzAVBgNVBAMUDnVzZXJAY2llbmEuY29tMR0wGwYJKoZI
hvcNAQkBFg51c2VyQGNpZW5hLmNvbTCBnzANBgkqhkiG9w0BAQEFAAOBjQAwgYkC
gYEAwvXiSzb9LZ6c7uNziUfKvoHO7wu/uiFC5YUpXbmVGuGZizbVrny0xnR85Dfe
+9R4diansfDhIhzOUl1XjN3YDeSS9OeF5YWNNE8XDhlz2d3rVzaN6hIhdotBkUjg
rUewjTg5OFR31QEyG3v8xR3CLgiE9xQELjZbSA07pD79zuUCAwEAAaNPME0wEwYD
VR0lBAwwCgYIKwYBBQUHAwIwNgYDVR0fBC8wLTAroCmgJ4YlaHR0cDovL3d3dy5l
eGFtcGxlLmNvbS9leGFtcGxlX2NhLmNybDANBgkqhkiG9w0BAQUFAAOBgQDAjkrY
6tDChmKbvr8w6Du/t8vHjTCoCIocHTN0qzWOeb1YsAGX89+TrWIuO1dFyYd+Z0KC
PDKB5j/ygml9Na+AklSYAVJIjvlzXKZrOaPmhZqDufi+rXWti/utVqY4VMW2+HKC
nXp37qWeuFLGyR1519Y1d6F/5XzqmvbwURuEug==
-----END CERTIFICATE-----"""

    CLIENT_CERT_INVALID = '''-----BEGIN CERTIFICATE-----
MIIDvTCCAqWgAwIBAgIBAjANBgkqhkiG9w0BAQUFADCBizELMAkGA1UEBhMCVVMx
CzAJBgNVBAgTAkNBMRIwEAYDVQQHEwlTb21ld2hlcmUxEzARBgNVBAoTCkNpZW5h
IEluYy4xHjAcBgkqhkiG9w0BCQEWD2FkbWluQGNpZW5hLmNvbTEmMCQGA1UEAxMd
RXhhbXBsZSBDZXJ0aWZpY2F0ZSBBdXRob3JpdHkwHhcNMTYwMzExMTg1MzM2WhcN
MTcwMzA2MTg1MzM2WjBnMQswCQYDVQQGEwJVUzELMAkGA1UECBMCQ0ExEzARBgNV
BAoTCkNpZW5hIEluYy4xFzAVBgNVBAMUDnVzZXJAY2llbmEuY29tMR0wGwYJKoZI
hvcNAQkBFg51c2VyQGNpZW5hLmNvbTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCC
AQoCggEBAOxemcBsPn9tZsCa5o2JA6sQDC7A6JgCNXXl2VFzKLNNvB9PS6D7ZBsQ
5An0zEDMNzi51q7lnrYg1XyiE4S8FzMGAFr94RlGMQJUbRD9V/oqszMX4k++iAOK
tIA1gr3x7Zi+0tkjVSVzXTmgNnhChAamdMsjYUG5+CY9WAicXyy+VEV3zTphZZDR
OjcjEp4m/TSXVPYPgYDXI40YZKX5BdvqykWtT/tIgZb48RS1NPyN/XkCYzl3bv21
qx7Mc0fcEbsJBIIRYTUkfxnsilcnmLxSYO+p+DZ9uBLBzcQt+4Rd5pLSfi21WM39
2Z2oOi3vs/OYAPAqgmi2JWOv3mePa/8CAwEAAaNPME0wEwYDVR0lBAwwCgYIKwYB
BQUHAwIwNgYDVR0fBC8wLTAroCmgJ4YlaHR0cDovL3d3dy5leGFtcGxlLmNvbS9l
eGFtcGxlX2NhLmNybDANBgkqhkiG9w0BAQUFAAOCAQEALBzMPDTIB6sLyPl0T6JV
MjOkyldAVhXWiQsTjaGQGJUUe1cmUJyZbUZEc13MygXMPOM4x7z6VpXGuq1c/Vxn
VzQ2fNnbJcIAHi/7G8W5/SQfPesIVDsHTEc4ZspPi5jlS/MVX3HOC+BDbOjdbwqP
RX0JEr+uOyhjO+lRxG8ilMRACoBUbw1eDuVDoEBgErSUC44pq5ioDw2xelc+Y6hQ
dmtYwfY0DbvwxHtA495frLyPcastDiT/zre7NL51MyUDPjjYjghNQEwvu66IKbQ3
T1tJBrgI7/WI+dqhKBFolKGKTDWIHsZXQvZ1snGu/FRYzg1l+R/jT8cRB9BDwhUt
yg==
-----END CERTIFICATE-----'''

    @classmethod
    def update_apps_version(cls):
        version = Onos.getVersion()
        major = int(version.split('.')[0])
        minor = int(version.split('.')[1])
        cordigmp_app_version = '2.0-SNAPSHOT'
        olt_app_version = '1.2-SNAPSHOT'
        if major > 1:
            cordigmp_app_version = '3.0-SNAPSHOT'
            olt_app_version = '2.0-SNAPSHOT'
        elif major == 1:
            if minor > 10:
                cordigmp_app_version = '3.0-SNAPSHOT'
                olt_app_version = '2.0-SNAPSHOT'
            elif minor <= 8:
                olt_app_version = '1.1-SNAPSHOT'
            cls.app_file = os.path.join(cls.test_path, '..', 'apps/ciena-cordigmp-{}.oar'.format(cordigmp_app_version))
            cls.table_app_file = os.path.join(cls.test_path, '..', 'apps/ciena-cordigmp-multitable-{}.oar'.format(cordigmp_app_version))
            cls.olt_app_file = os.path.join(cls.test_path, '..', 'apps/olt-app-{}.oar'.format(olt_app_version))

    @classmethod
    def onos_load_config(cls, app, config):
        status, code = OnosCtrl.config(config)
        if status is False:
            log_test.info('JSON config request for app %s returned status %d' %(app, code))
            assert_equal(status, True)
        time.sleep(2)

    @classmethod
    def onos_aaa_load(cls):
        aaa_dict = {'apps' : { 'org.opencord.aaa' : { 'AAA' : { 'radiusSecret': 'radius_password',
                                                                'radiusIp': '172.17.0.2' } } } }
        radius_ip = os.getenv('ONOS_AAA_IP') or '172.17.0.2'
        aaa_dict['apps']['org.opencord.aaa']['AAA']['radiusIp'] = radius_ip
        cls.onos_load_config('org.opencord.aaa', aaa_dict)

    @classmethod
    def setUpClass(cls):
        cls.update_apps_version()
        cls.voltha = VolthaCtrl(cls.VOLTHA_HOST, rest_port = cls.VOLTHA_REST_PORT)
        cls.install_app_table()
        cls.olt = OltConfig(olt_conf_file = cls.olt_conf_file)
        cls.port_map, cls.port_list = cls.olt.olt_port_map()
        cls.switches = cls.port_map['switches']
        cls.num_ports = cls.port_map['num_ports']
        if cls.num_ports > 1:
              cls.num_ports -= 1 ##account for the tx port
        cls.activate_apps(cls.apps + cls.olt_apps)
        cls.onos_aaa_load()

    @classmethod
    def tearDownClass(cls):
        '''Deactivate the olt apps and restart OVS back'''
        apps = cls.olt_apps + ( cls.table_app,)
        for app in apps:
            onos_ctrl = OnosCtrl(app)
            onos_ctrl.deactivate()
        cls.install_app_igmp()

    @classmethod
    def install_app_igmp(cls):
        ##Uninstall the table app on class exit
        OnosCtrl.uninstall_app(cls.table_app)
        time.sleep(2)
        log_test.info('Installing back the cord igmp app %s for subscriber test on exit' %(cls.app_file))
        OnosCtrl.install_app(cls.app_file)

    def remove_olt(self, switch_map):
        controller = get_controller()
        auth = ('karaf', 'karaf')
        #remove subscriber for every port on all the voltha devices
        for device, device_map in switch_map.iteritems():
            uni_ports = device_map['ports']
            uplink_vlan = device_map['uplink_vlan']
            for port in uni_ports:
                rest_url = 'http://{}:8181/onos/olt/oltapp/{}/{}'.format(controller,
                                                                         device,
                                                                         port)
                resp = requests.delete(rest_url, auth = auth)
                if resp.status_code not in [204, 202, 200]:
                      log_test.error('Error deleting subscriber for device %s on port %s' %(device, port))
                else:
                      log_test.info('Deleted subscriber for device %s on port  %s' %(device, port))
        OnosCtrl.uninstall_app(self.olt_app_file)

    def config_olt(self, switch_map):
        controller = get_controller()
        auth = ('karaf', 'karaf')
        #configure subscriber for every port on all the voltha devices
        for device, device_map in switch_map.iteritems():
            uni_ports = device_map['ports']
            uplink_vlan = device_map['uplink_vlan']
            for port in uni_ports:
                vlan = port
                rest_url = 'http://{}:8181/onos/olt/oltapp/{}/{}/{}'.format(controller,
                                                                            device,
                                                                            port,
                                                                            vlan)
                resp = requests.post(rest_url, auth = auth)
                #assert_equal(resp.ok, True)

    def voltha_uni_port_toggle(self, uni_port = None):
        ## Admin state of port is down and up
        if not uni_port:
           uni_port = self.INTF_RX_DEFAULT
        cmd = 'ifconfig {} down'.format(uni_port)
        os.system(cmd)
        log_test.info('Admin state of uni_port is down')
        time.sleep(30)
        cmd = 'ifconfig {} up'.format(uni_port)
        os.system(cmd)
        log_test.info('Admin state of uni_port is up now')
        time.sleep(30)
        return


    @classmethod
    def install_app_table(cls):
        ##Uninstall the existing app if any
        OnosCtrl.uninstall_app(cls.table_app)
        time.sleep(2)
        log_test.info('Installing the multi table app %s for subscriber test' %(cls.table_app_file))
        OnosCtrl.install_app(cls.table_app_file)
        time.sleep(3)

    @classmethod
    def activate_apps(cls, apps):
        for app in apps:
            onos_ctrl = OnosCtrl(app)
            status, _ = onos_ctrl.activate()
            assert_equal(status, True)
            time.sleep(2)

    def tls_flow_check(self, olt_uni_port, cert_info = None):
        def tls_fail_cb():
             log_test.info('TLS verification failed')
        if cert_info is None:
           tls = TLSAuthTest(fail_cb = tls_fail_cb, intf = olt_uni_port)
           log_test.info('Running subscriber %s tls auth test with valid TLS certificate' %olt_uni_port)
           tls.runTest()
           if tls.failTest is True:
              self.success = False
           assert_equal(tls.failTest, False)
        if cert_info == "no_cert":
           tls = TLSAuthTest(fail_cb = tls_fail_cb, intf = olt_uni_port, client_cert = '')
           log_test.info('Running subscriber %s tls auth test with no TLS certificate' %olt_uni_port)
           tls.runTest()
           if tls.failTest is False:
              self.success = False
           assert_equal(tls.failTest, True)
        if cert_info == "invalid_cert":
           tls = TLSAuthTest(fail_cb = tls_fail_cb, intf = olt_uni_port, client_cert = self.CLIENT_CERT_INVALID)
           log_test.info('Running subscriber %s tls auth test with invalid TLS certificate' %olt_uni_port)
           tls.runTest()
           if tls.failTest is False:
              self.success = False
           assert_equal(tls.failTest, True)
        if cert_info == "same_cert":
           tls = TLSAuthTest(fail_cb = tls_fail_cb, intf = olt_uni_port)
           log_test.info('Running subscriber %s tls auth test with invalid TLS certificate' %olt_uni_port)
           tls.runTest()
           if tls.failTest is False:
              self.success = False
           assert_equal(tls.failTest, True)
        if cert_info == "app_deactivate" or cert_info == "restart_radius" or cert_info == "disable_olt_device" or \
           cert_info == "uni_port_admin_down" or cert_info == "restart_olt_device" or cert_info == "restart_onu_device":
           tls = TLSAuthTest(fail_cb = tls_fail_cb, intf = olt_uni_port, client_cert = self.CLIENT_CERT_INVALID)
           log_test.info('Running subscriber %s tls auth test with %s' %(olt_uni_port,cert_info))
           tls.runTest()
           if tls.failTest is False:
              self.success = False
           assert_equal(tls.failTest, True)
        self.test_status = True
        return self.test_status

    def test_olt_enable_disable(self):
        log_test.info('Enabling OLT type %s, MAC %s' %(self.OLT_TYPE, self.OLT_MAC))
        device_id, status = self.voltha.enable_device(self.OLT_TYPE, self.OLT_MAC)
        assert_not_equal(device_id, None)
        try:
            assert_equal(status, True)
            time.sleep(10)
        finally:
            self.voltha.disable_device(device_id, delete = True)

    def test_ponsim_enable_disable(self):
        log_test.info('Enabling ponsim_olt')
        ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
        device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
        assert_not_equal(device_id, None)
        try:
            assert_equal(status, True)
            time.sleep(10)
        finally:
            self.voltha.disable_device(device_id, delete = True)

    def test_subscriber_with_voltha_for_eap_tls_authentication(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Issue  auth request packets from CORD TESTER voltha test module acting as a subscriber..
        4. Validate that eap tls valid auth packets are being exchanged between subscriber, onos and freeradius.
        5. Verify that subscriber is authenticated successfully.
        """
        log_test.info('Enabling ponsim_olt')
        ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
        device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
        assert_not_equal(device_id, None)
        if status == False:
            self.voltha.disable_device(device_id, delete = True)
        assert_equal(status, True)
        time.sleep(10)
        switch_map = None
        olt_configured = False
        voltha = VolthaCtrl(self.VOLTHA_HOST,
                            rest_port = self.VOLTHA_REST_PORT,
                            uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
        try:
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            if not switch_map:
                log_test.info('No voltha devices found')
                return
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)
            auth_status = self.tls_flow_check(self.INTF_RX_DEFAULT)
            assert_equal(auth_status, True)
        finally:
            if switch_map is not None:
                if olt_configured is True:
                    self.remove_olt(switch_map)
                self.voltha.disable_device(device_id, delete = True)
                time.sleep(10)
                OnosCtrl.uninstall_app(self.olt_app_name)

    @deferred(TESTCASE_TIMEOUT)
    def test_subscriber_with_voltha_for_eap_tls_authentication_failure(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        4. Validate that eap tls without cert auth packet is being exchanged between subscriber, onos and freeradius.
        5. Verify that subscriber authentication is unsuccessful..
        """
        df = defer.Deferred()
        def tls_flow_check_with_no_cert_scenario(df):
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                                rest_port = self.VOLTHA_REST_PORT,
                                uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)
            auth_status = self.tls_flow_check(self.INTF_RX_DEFAULT, cert_info = "no_cert")
            try:
                assert_equal(auth_status, True)
                assert_equal(status, True)
                time.sleep(10)
            finally:
                self.remove_olt(switch_map)
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)

        reactor.callLater(0, tls_flow_check_with_no_cert_scenario, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_subscriber_with_voltha_for_eap_tls_authentication_using_invalid_cert(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Issue  tls auth packets and exchange invalid cert from CORD TESTER voltha test module acting as a subscriber..
        4. Validate that eap tls with invalid cert auth packet is being exchanged between subscriber, onos and freeradius.
        5. Verify that subscriber authentication is unsuccessful..
        """
        df = defer.Deferred()
        def tls_flow_check_with_invalid_cert_scenario(df):
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)
            auth_status = self.tls_flow_check(self.INTF_RX_DEFAULT, cert_info = "invalid_cert")
            try:
                assert_equal(auth_status, True)
                assert_equal(status, True)
                time.sleep(10)
            finally:
                self.remove_olt(switch_map)
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_with_invalid_cert_scenario, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_subscriber_with_voltha_for_multiple_invalid_authentication_attempts(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Issue  tls auth packets and exchange invalid cert from CORD TESTER voltha test module acting as a subscriber for multiple times.
        4. Validate that eap tls with invalid cert auth packet is being exchanged between subscriber, onos and freeradius.
        5. Verify that subscriber authentication is unsuccessful..
        """
        df = defer.Deferred()
        def tls_flow_check_with_no_cert_scenario(df):
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)
            auth_status = self.tls_flow_check(self.INTF_RX_DEFAULT, cert_info = "invalid_cert")
            auth_status = self.tls_flow_check(self.INTF_RX_DEFAULT, cert_info = "invalid_cert")
            auth_status = self.tls_flow_check(self.INTF_RX_DEFAULT, cert_info = "no_cert")
            auth_status = self.tls_flow_check(self.INTF_RX_DEFAULT, cert_info = "invalid_cert")
            try:
                assert_equal(auth_status, True)
                assert_equal(status, True)
                time.sleep(10)
            finally:
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_with_no_cert_scenario, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_subscriber_with_voltha_for_eap_tls_authentication_with_aaa_app_deactivation(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        4. Validate that eap tls without sending client hello, it's not being exchanged between client, onos and freeradius.
        5. Verify that subscriber authentication is unsuccessful..
        """
        df = defer.Deferred()
        def tls_flow_check_deactivating_app(df):
            aaa_app = ["org.opencord.aaa"]
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)

            thread1 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_RX_DEFAULT,"app_deactivate",))
            thread2 = threading.Thread(target = self.deactivate_apps, args = (aaa_app,))
            thread1.start()
            time.sleep(randint(1,2))
            log_test.info('Restart aaa app in onos during tls auth flow check on voltha')
            thread2.start()
            time.sleep(10)
            thread1.join()
            thread2.join()
            try:
        #        assert_equal(status, True)
                assert_equal(self.success, True)
                time.sleep(10)
            finally:
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_deactivating_app, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_subscriber_with_voltha_for_eap_tls_authentication_restarting_radius_server(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        4. Validate that eap tls with restart of radius server and packets are being exchanged between subscriber, onos and freeradius.
        5. Verify that subscriber authentication is unsuccessful..
        """
        df = defer.Deferred()
        def tls_flow_check_restarting_radius(df):
            aaa_app = ["org.opencord.aaa"]
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)

            thread1 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_RX_DEFAULT,"restart_radius"))
            thread2 = threading.Thread(target = cord_test_radius_restart)
            thread1.start()
            time.sleep(randint(1,2))
            log_test.info('Restart radius server during tls auth flow check on voltha')
            thread2.start()
            time.sleep(10)
            thread1.join()
            thread2.join()
            try:
        #        assert_equal(status, True)
                assert_equal(self.success, True)
                time.sleep(10)
            finally:
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_restarting_radius, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_subscriber_with_voltha_for_eap_tls_authentication_with_disabled_olt(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        5. Validate that eap tls packets are being exchanged between subscriber, onos and freeradius.
        6. Verify that subscriber authenticated successfully.
        7. Disable olt which is seen in voltha and issue tls auth packets from subscriber.
        8. Validate that eap tls packets are not being exchanged between subscriber, onos and freeradius.
        9. Verify that subscriber authentication is unsuccessful..
        """
        df = defer.Deferred()
        def tls_flow_check_operating_olt_state(df):
            aaa_app = ["org.opencord.aaa"]
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)

            thread1 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_RX_DEFAULT, "disable_olt_device",))
            thread2 = threading.Thread(target = self.voltha.disable_device, args = (device_id,))
            thread1.start()
            time.sleep(randint(1,2))
            log_test.info('Disable the ponsim olt device during tls auth flow check on voltha')
            thread2.start()
            time.sleep(10)
            thread1.join()
            thread2.join()
            try:
        #        assert_equal(status, True)
                assert_equal(self.success, True)
                time.sleep(10)
            finally:
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_operating_olt_state, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_subscriber_with_voltha_for_eap_tls_authentication_disabling_uni_port(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        5. Validate that eap tls packets are being exchanged between subscriber, onos and freeradius.
        6. Verify that subscriber authenticated successfully.
        7. Disable uni port which is seen in voltha and issue tls auth packets from subscriber.
        8. Validate that eap tls packets are not being exchanged between subscriber, onos and freeradius.
        9. Verify that subscriber authentication is unsuccessful..
        """
        df = defer.Deferred()
        def tls_flow_check_operating_olt_state(df):
            aaa_app = ["org.opencord.aaa"]
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)

            thread1 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_RX_DEFAULT, "uni_port_admin_down",))
            thread2 = threading.Thread(target = self.voltha_uni_port_toggle)
            thread1.start()
            time.sleep(randint(1,2))
            log_test.info('Admin state of uni port is down and up after delay of 30 sec during tls auth flow check on voltha')
            thread2.start()
            time.sleep(10)
            thread1.join()
            thread2.join()
            try:
        #        assert_equal(status, True)
                assert_equal(self.success, True)
                time.sleep(10)
            finally:
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_operating_olt_state, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_subscriber_with_voltha_for_eap_tls_authentication_restarting_olt(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        5. Validate that eap tls packets are being exchanged between subscriber, onos and freeradius.
        6. Verify that subscriber authenticated successfully.
        7. Restart olt which is seen in voltha and issue tls auth packets from subscriber.
        8. Validate that eap tls packets are not being exchanged between subscriber, onos and freeradius.
        9. Verify that subscriber authentication is unsuccessful..
        """
        df = defer.Deferred()
        def tls_flow_check_operating_olt_state(df):
            aaa_app = ["org.opencord.aaa"]
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)

            thread1 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_RX_DEFAULT, "restart_olt_device",))
            thread2 = threading.Thread(target = self.voltha.restart_device, args = (device_id,))
            thread1.start()
            time.sleep(randint(1,2))
            log_test.info('Restart the ponsim olt device during tls auth flow check on voltha')
            thread2.start()
            time.sleep(10)
            thread1.join()
            thread2.join()
            try:
        #        assert_equal(status, True)
                assert_equal(self.success, True)
                time.sleep(10)
            finally:
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_operating_olt_state, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_subscriber_with_voltha_for_eap_tls_authentication_restarting_onu(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        5. Validate that eap tls packets are being exchanged between subscriber, onos and freeradius.
        6. Verify that subscriber authenticated successfully.
        7. Restart onu which is seen in voltha and issue tls auth packets from subscriber.
        8. Validate that eap tls packets are not being exchanged between subscriber, onos and freeradius.
        9. Verify that subscriber authentication is unsuccessful..
        """
        df = defer.Deferred()
        def tls_flow_check_operating_olt_state(df):
            aaa_app = ["org.opencord.aaa"]
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            devices_list = self.voltha.get_devices()
            log_test.info('All available devices on voltha = %s'%devices_list['items'])

            onu_device_id = devices_list['items'][1]['id']
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)
            devices_list = self.voltha.get_devices()
            thread1 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_RX_DEFAULT, "restart_onu_device",))
            thread2 = threading.Thread(target = self.voltha.restart_device, args = (onu_device_id,))
            thread1.start()
            time.sleep(randint(1,2))
            log_test.info('Restart the ponsim oon device during tls auth flow check on voltha')
            thread2.start()
            time.sleep(10)
            thread1.join()
            thread2.join()
            try:
        #        assert_equal(status, True)
                assert_equal(self.success, True)
                time.sleep(10)
            finally:
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_operating_olt_state, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_two_subscribers_with_voltha_for_eap_tls_authentication(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT is detected and ONU ports(nni and 2 uni's) are being seen.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Bring up two Residential subscribers from cord-tester and issue tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        4. Validate that eap tls valid auth packets are being exchanged between two subscriber, onos and freeradius.
        5. Verify that two subscribers are authenticated successfully.
        """

        df = defer.Deferred()
        def tls_flow_check_on_two_subscriber_same_olt_device(df):
            aaa_app = ["org.opencord.aaa"]
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            devices_list = self.voltha.get_devices()
            log_test.info('All available devices on voltha = %s'%devices_list['items'])

            onu_device_id = devices_list['items'][1]['id']
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)
            devices_list = self.voltha.get_devices()
            thread1 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_RX_DEFAULT,))
            thread2 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_2_RX_DEFAULT,))
            thread1.start()
            time.sleep(randint(1,2))
            log_test.info('Initiating tls auth packets from one more subscriber on same olt device which is deteced on voltha')
            thread2.start()
            time.sleep(10)
            thread1.join()
            thread2.join()
            try:
        #        assert_equal(status, True)
                assert_equal(self.success, True)
                time.sleep(10)
            finally:
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_on_two_subscriber_same_olt_device, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_two_subscribers_with_voltha_for_eap_tls_authentication_using_same_certificates(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT is detected and ONU ports(nni and 2 uni's) are being seen.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Bring up two Residential subscribers from cord-tester and issue tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        4. Validate that two valid certificates are being exchanged between two subscriber, onos and freeradius.
        5. Verify that two subscribers are not authenticated.
        """

        df = defer.Deferred()
        def tls_flow_check_on_two_subscriber_same_olt_device(df):
            aaa_app = ["org.opencord.aaa"]
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            devices_list = self.voltha.get_devices()
            log_test.info('All available devices on voltha = %s'%devices_list['items'])

            onu_device_id = devices_list['items'][1]['id']
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)
            devices_list = self.voltha.get_devices()
            thread1 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_RX_DEFAULT,))
            thread2 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_2_RX_DEFAULT, "same_cert",))
            thread1.start()
            time.sleep(randint(1,2))
            log_test.info('Initiating tls auth packets from one more subscriber on same olt device which is deteced on voltha')
            thread2.start()
            time.sleep(10)
            thread1.join()
            thread2.join()
            try:
        #        assert_equal(status, True)
                 assert_equal(self.success, True)
                 time.sleep(10)
            finally:
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_on_two_subscriber_same_olt_device, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_two_subscribers_with_voltha_for_eap_tls_authentication_initiating_invalid_tls_packets_for_one_subscriber(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT is detected and ONU ports(nni and 2 uni's) are being seen.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Bring up two Residential subscribers from cord-tester and issue tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        4. Validate that eap tls valid auth packets are being exchanged between valid subscriber, onos and freeradius.
        5. Validate that eap tls valid auth packets are being exchanged between invalid client, onos and freeradius.
        6. Verify that valid subscriber authenticated successfully.
        7. Verify that invalid subscriber are not authenticated successfully.
        """

        df = defer.Deferred()
        def tls_flow_check_on_two_subscriber_same_olt_device(df):
            aaa_app = ["org.opencord.aaa"]
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            devices_list = self.voltha.get_devices()
            log_test.info('All available devices on voltha = %s'%devices_list['items'])

            onu_device_id = devices_list['items'][1]['id']
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)
            devices_list = self.voltha.get_devices()
            thread1 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_RX_DEFAULT,))
            thread2 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_2_RX_DEFAULT, "no_cert",))
            thread1.start()
            time.sleep(randint(1,2))
            log_test.info('Initiating tls auth packets from one more subscriber on same olt device which is deteced on voltha')
            thread2.start()
            time.sleep(10)
            thread1.join()
            thread2.join()
            try:
        #        assert_equal(status, True)
                 assert_equal(self.success, True)
                 time.sleep(10)
            finally:
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_on_two_subscriber_same_olt_device, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_two_subscribers_with_voltha_for_eap_tls_authentication_initiating_invalid_cert_for_one_subscriber(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT is detected and ONU ports(nni and 2 uni's) are being seen.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Bring up two Residential subscribers from cord-tester and issue tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        4. Validate that eap tls valid auth packets are being exchanged between valid subscriber, onos and freeradius.
        5. Validate that eap tls invalid cert auth packets are being exchanged between invalid subscriber, onos and freeradius.
        6. Verify that valid subscriber authenticated successfully.
        7. Verify that invalid subscriber are not authenticated successfully.
        """

        df = defer.Deferred()
        def tls_flow_check_on_two_subscriber_same_olt_device(df):
            aaa_app = ["org.opencord.aaa"]
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            devices_list = self.voltha.get_devices()
            log_test.info('All available devices on voltha = %s'%devices_list['items'])

            onu_device_id = devices_list['items'][1]['id']
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)
            devices_list = self.voltha.get_devices()
            thread1 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_RX_DEFAULT,))
            thread2 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_2_RX_DEFAULT, "invalid_cert",))
            thread1.start()
            time.sleep(randint(1,2))
            log_test.info('Initiating tls auth packets from one more subscriber on same olt device which is deteced on voltha')
            thread2.start()
            time.sleep(10)
            thread1.join()
            thread2.join()
            try:
        #        assert_equal(status, True)
                assert_equal(self.success, True)
                time.sleep(10)
            finally:
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_on_two_subscriber_same_olt_device, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_two_subscribers_with_voltha_for_eap_tls_authentication_with_one_uni_port_disabled(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Bring up freeradius server container using CORD TESTER and make sure that ONOS have connectivity to freeradius server.
        3. Bring up two Residential subscribers from cord-tester and issue tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        5. Validate that eap tls packets are being exchanged between two subscriber, onos and freeradius.
        6. Verify that subscriber authenticated successfully.
        7. Disable one of the uni port which is seen in voltha and issue tls auth packets from subscriber.
        8. Validate that eap tls packets are not being exchanged between one subscriber, onos and freeradius.
        9. Verify that subscriber authentication is unsuccessful..
        10. Verify that other subscriber authenticated successfully.
        """

        df = defer.Deferred()
        def tls_flow_check_on_two_subscriber_same_olt_device(df):
            aaa_app = ["org.opencord.aaa"]
            log_test.info('Enabling ponsim_olt')
            ponsim_address = '{}:50060'.format(self.VOLTHA_HOST)
            device_id, status = self.voltha.enable_device('ponsim_olt', address = ponsim_address)
            devices_list = self.voltha.get_devices()
            log_test.info('All available devices on voltha = %s'%devices_list['items'])

            onu_device_id = devices_list['items'][1]['id']
            assert_not_equal(device_id, None)
            voltha = VolthaCtrl(self.VOLTHA_HOST,
                              rest_port = self.VOLTHA_REST_PORT,
                              uplink_vlan_map = self.VOLTHA_UPLINK_VLAN_MAP)
            time.sleep(10)
            switch_map = None
            olt_configured = False
            switch_map = voltha.config(fake = self.VOLTHA_CONFIG_FAKE)
            log_test.info('Installing OLT app')
            OnosCtrl.install_app(self.olt_app_file)
            time.sleep(5)
            log_test.info('Adding subscribers through OLT app')
            self.config_olt(switch_map)
            olt_configured = True
            time.sleep(5)
            devices_list = self.voltha.get_devices()
            thread1 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_RX_DEFAULT,))
            thread2 = threading.Thread(target = self.tls_flow_check, args = (self.INTF_2_RX_DEFAULT, "uni_port_admin_down",))
            thread1.start()
            time.sleep(randint(1,2))
            log_test.info('Initiating tls auth packets from one more subscriber on same olt device which is deteced on voltha')
            thread2.start()
            time.sleep(10)
            thread1.join()
            thread2.join()
            try:
        #        assert_equal(status, True)
                assert_equal(self.success, True)
                time.sleep(10)
            finally:
                self.voltha.disable_device(device_id, delete = True)
            df.callback(0)
        reactor.callLater(0, tls_flow_check_on_two_subscriber_same_olt_device, df)
        return df

    @deferred(TESTCASE_TIMEOUT)
    def test_subscriber_with_voltha_for_dhcp_request(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscrber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip from dhcp server successfully.
        """

    def test_subscriber_with_voltha_for_dhcp_request_with_invalid_broadcast_source_mac(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request with invalid source mac broadcast from residential subscrber to dhcp server which is running as onos app.
        4. Verify that subscriber should not get ip from dhcp server.
        """

    def test_subscriber_with_voltha_for_dhcp_request_with_invalid_multicast_source_mac(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request with invalid source mac multicast from residential subscrber to dhcp server which is running as onos app.
        4. Verify that subscriber should not get ip from dhcp server.
        """

    def test_subscriber_with_voltha_for_dhcp_request_with_invalid_source_mac(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request with invalid source mac zero from residential subscrber to dhcp server which is running as onos app.
        4. Verify that subscriber should not get ip from dhcp server.
        """

    def test_subscriber_with_voltha_for_dhcp_request_and_release(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscrber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip from dhcp server successfully.
        5. Send dhcp release from residential subscrber to dhcp server which is running as onos app.
        6  Verify that subscriber should not get ip from dhcp server, ping to gateway.
        """

    def test_subscriber_with_voltha_for_dhcp_starvation_positive_scenario(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip from dhcp server successfully.
        5. Repeat step 3 and 4 for 10 times.
        6  Verify that subscriber should get ip from dhcp server.
        """

    def test_subscriber_with_voltha_for_dhcp_starvation_negative_scenario(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber without of pool ip to dhcp server which is running as onos app.
        4. Verify that subscriber should not get ip from dhcp server.
        5. Repeat steps 3 and 4 for 10 times.
        6  Verify that subscriber should not get ip from dhcp server.
        """
    def test_subscriber_with_voltha_for_dhcp_sending_multiple_discover(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip from dhcp server successfully.
        5. Repeat step 3 for 50 times.
        6  Verify that subscriber should get same ip which was received from 1st discover from dhcp server.
        """
    def test_subscriber_with_voltha_for_dhcp_sending_multiple_request(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip from dhcp server successfully.
        5. Send DHCP request to dhcp server which is running as onos app.
        6. Repeat step 5 for 50 times.
        7. Verify that subscriber should get same ip which was received from 1st discover from dhcp server.
        """

    def test_subscriber_with_voltha_for_dhcp_requesting_desired_ip_address(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request with desired ip address from residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip which was requested in step 3 from dhcp server successfully.
        """

    def test_subscriber_with_voltha_for_dhcp_requesting_desired_out_pool_ip_address(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request with desired out of pool ip address from residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscriber should not get ip which was requested in step 3 from dhcp server, and its offered only within dhcp pool of ip.
        """
    def test_subscriber_with_voltha_for_dhcp_deactivate_dhcp_app_in_onos(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip from dhcp server successfully.
        5. Deactivate dhcp server app in onos.
        6. Repeat step 3.
        7. Verify that subscriber should not get ip from dhcp server, and ping to gateway.
        """
    def test_subscriber_with_voltha_for_dhcp_renew_time(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip from dhcp server successfully.
        5. Send dhcp renew packet to dhcp server which is running as onos app.
        6. Repeat step 4.
        """
    def test_subscriber_with_voltha_for_dhcp_rebind_time(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip from dhcp server successfully.
        5. Send dhcp rebind packet to dhcp server which is running as onos app.
        6. Repeat step 4.
        """
    def test_subscriber_with_voltha_for_dhcp_disable_olt_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip from dhcp server successfully.
        5. Disable olt devices which is being detected in voltha CLI.
        6. Repeat step 3.
        7. Verify that subscriber should not get ip from dhcp server, and ping to gateway.
        """
    def test_subscriber_with_voltha_for_dhcp_disable_enable_olt_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip from dhcp server successfully.
        5. Disable olt devices which is being detected in voltha CLI.
        6. Repeat step 3.
        7. Verify that subscriber should not get ip from dhcp server, and ping to gateway.
        8. Enable olt devices which is being detected in voltha CLI.
        9. Repeat steps 3 and 4.
        """
    def test_subscriber_with_voltha_for_dhcp_disable_onu_port_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip from dhcp server successfully.
        5. Disable onu port which is being detected in voltha CLI.
        6. Repeat step 3.
        7. Verify that subscriber should not get ip from dhcp server, and ping to gateway.
        """
    def test_subscriber_with_voltha_for_dhcp_disable_enable_onu_port_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscriber get ip from dhcp server successfully.
        5. Disable onu port which is being detected in voltha CLI.
        6. Repeat step 3.
        7. Verify that subscriber should not get ip from dhcp server, and ping to gateway.
        8. Enable onu port which is being detected in voltha CLI.
        9. Repeat steps 3 and 4.
        """

    def test_two_subscriber_with_voltha_for_dhcp_discover(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to dhcp server which is running as onos app.
        4. Verify that subscribers had got different ips from dhcp server successfully.
        """

    def test_two_subscriber_with_voltha_for_dhcp_multiple_discover(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to dhcp server which is running as onos app.
        4. Verify that subscribers had got ip from dhcp server successfully.
        5. Repeat step 3 and 4 for 10 times for both subscribers.
        6  Verify that subscribers should get same ips which are offered the first time from dhcp server.
        """
    def test_two_subscriber_with_voltha_for_dhcp_multiple_discover_for_one_subscriber(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to dhcp server which is running as onos app.
        4. Verify that subscribers had got ip from dhcp server successfully.
        5. Repeat step 3 and 4 for 10 times for only one subscriber and ping to gateway from other subscriber.
        6  Verify that subscriber should get same ip which is offered the first time from dhcp server and other subscriber ping to gateway should not failed
        """
    def test_two_subscriber_with_voltha_for_dhcp_discover_desired_ip_address_for_one_subscriber(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from one residential subscriber to dhcp server which is running as onos app.
        3. Send dhcp request with desired ip from other residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscribers had got different ips (one subscriber desired ip and other subscriber random ip) from dhcp server successfully.
        """
    def test_two_subscriber_with_voltha_for_dhcp_discover_within_and_wothout_dhcp_pool_ip_addresses(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request with desired wihtin dhcp pool ip from one residential subscriber to dhcp server which is running as onos app.
        3. Send dhcp request with desired without in dhcp pool ip from other residential subscriber to dhcp server which is running as onos app.
        4. Verify that subscribers had got different ips (both subscriber got random ips within dhcp pool) from dhcp server successfully.
        """
    def test_two_subscriber_with_voltha_for_dhcp_disable_onu_port_for_one_subscriber(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to dhcp server which is running as onos app.
        4. Verify that subscribers had got ip from dhcp server successfully.
        5. Disable onu port on which access one subscriber and ping to gateway from other subscriber.
        6. Repeat step 3 and 4 for one subscriber where uni port is down.
        7. Verify that subscriber should not get ip from dhcp server and other subscriber ping to gateway should not failed.
        """
    def test_two_subscriber_with_voltha_for_dhcp_disable_enable_onu_port_for_one_subscriber(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to dhcp server which is running as onos app.
        4. Verify that subscribers had got ip from dhcp server successfully.
        5. Disable onu port on which access one subscriber and ping to gateway from other subscriber.
        6. Repeat step 3 and 4 for one subscriber where uni port is down.
        7. Verify that subscriber should not get ip from dhcp server and other subscriber ping to gateway should not failed.
        8. Enable onu port on which was disable at step 5 and ping to gateway from other subscriber.
        9. Repeat step 3 and 4 for one subscriber where uni port is up now.
        10. Verify that subscriber should get ip from dhcp server and other subscriber ping to gateway should not failed.
        """
    def test_two_subscriber_with_voltha_for_dhcp_disable_olt_detected_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to dhcp server which is running as onos app.
        4. Verify that subscribers had got ip from dhcp server successfully.
        5. Start pinging continuously from one subscriber and repeat steps 3 and 4 for other subscriber.
        6. Disable the olt device which is detected in voltha.
        7. Verify that subscriber should not get ip from dhcp server and other subscriber ping to gateway should failed.
        """
    def test_two_subscriber_with_voltha_for_dhcp_disable_enable_olt_detected_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to dhcp server which is running as onos app.
        4. Verify that subscribers had got ip from dhcp server successfully.
        5. Start pinging continuously from one subscriber and repeat steps 3 and 4 for other subscriber.
        6. Disable the olt device which is detected in voltha.
        7. Verify that subscriber should not get ip from dhcp server and other subscriber ping to gateway should failed.
        8. Enable the olt device which is detected in voltha.
        9. Verify that subscriber should get ip from dhcp server and other subscriber ping to gateway should not failed.
        """
    def test_two_subscriber_with_voltha_for_dhcp_pause_olt_detected_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to dhcp server which is running as onos app.
        4. Verify that subscribers had got ip from dhcp server successfully.
        5. Start pinging continuously from one subscriber and repeat steps 3 and 4 for other subscriber.
        6. Pause the olt device which is detected in voltha.
        7. Verify that subscriber should not get ip from dhcp server and other subscriber ping to gateway should failed.
        """
    def test_subscriber_with_voltha_for_dhcpRelay_dhcp_request(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscrber to external dhcp server.
        4. Verify that subscriber get ip from external dhcp server successfully.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_dhcp_request_with_invalid_broadcast_source_mac(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request with invalid source mac broadcast from residential subscrber to external dhcp server.
        4. Verify that subscriber should not get ip from external dhcp server.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_dhcp_request_with_invalid_multicast_source_mac(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are is up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request with invalid source mac multicast from residential subscrber to external dhcp server.
        4. Verify that subscriber should not get ip from external dhcp server.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_dhcp_request_with_invalid_source_mac(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request with invalid source mac zero from residential subscrber to external dhcp server.
        4. Verify that subscriber should not get ip from external dhcp server.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_dhcp_request_and_release(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscrber to external dhcp server.
        4. Verify that subscriber get ip from external dhcp server successfully.
        5. Send dhcp release from residential subscrber to external dhcp server.
        6  Verify that subscriber should not get ip from external dhcp server, ping to gateway.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_starvation(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to external dhcp server.
        4. Verify that subscriber get ip from external dhcp server. successfully.
        5. Repeat step 3 and 4 for 10 times.
        6  Verify that subscriber should get ip from external dhcp server..
        """

    def test_subscriber_with_voltha_for_dhcpRelay_starvation_negative_scenario(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber without of pool ip to external dhcp server.
        4. Verify that subscriber should not get ip from external dhcp server..
        5. Repeat steps 3 and 4 for 10 times.
        6  Verify that subscriber should not get ip from external dhcp server..
        """
    def test_subscriber_with_voltha_for_dhcpRelay_sending_multiple_discover(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to external dhcp server.
        4. Verify that subscriber get ip from external dhcp server. successfully.
        5. Repeat step 3 for 50 times.
        6  Verify that subscriber should get same ip which was received from 1st discover from external dhcp server..
        """
    def test_subscriber_with_voltha_for_dhcpRelay_sending_multiple_request(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to external dhcp server.
        4. Verify that subscriber get ip from external dhcp server. successfully.
        5. Send DHCP request to external dhcp server.
        6. Repeat step 5 for 50 times.
        7. Verify that subscriber should get same ip which was received from 1st discover from external dhcp server..
        """

    def test_subscriber_with_voltha_for_dhcpRelay_requesting_desired_ip_address(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request with desired ip address from residential subscriber to external dhcp server.
        4. Verify that subscriber get ip which was requested in step 3 from external dhcp server. successfully.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_requesting_desired_out_of_pool_ip_address(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request with desired out of pool ip address from residential subscriber to external dhcp server.
        4. Verify that subscriber should not get ip which was requested in step 3 from external dhcp server., and its offered only within dhcp pool of ip.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_deactivating_dhcpRelay_app_in_onos(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to external dhcp server.
        4. Verify that subscriber get ip from external dhcp server. successfully.
        5. Deactivate dhcp server app in onos.
        6. Repeat step 3.
        7. Verify that subscriber should not get ip from external dhcp server., and ping to gateway.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_renew_time(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to external dhcp server.
        4. Verify that subscriber get ip from external dhcp server. successfully.
        5. Send dhcp renew packet to external dhcp server.
        6. Repeat step 4.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_rebind_time(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to external dhcp server.
        4. Verify that subscriber get ip from external dhcp server. successfully.
        5. Send dhcp rebind packet to external dhcp server.
        6. Repeat step 4.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_disable_olt_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to external dhcp server.
        4. Verify that subscriber get ip from external dhcp server. successfully.
        5. Disable olt devices which is being detected in voltha CLI.
        6. Repeat step 3.
        7. Verify that subscriber should not get ip from external dhcp server., and ping to gateway.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_toggling_olt_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to external dhcp server.
        4. Verify that subscriber get ip from external dhcp server. successfully.
        5. Disable olt devices which is being detected in voltha CLI.
        6. Repeat step 3.
        7. Verify that subscriber should not get ip from external dhcp server., and ping to gateway.
        8. Enable olt devices which is being detected in voltha CLI.
        9. Repeat steps 3 and 4.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_disable_onu_port_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to external dhcp server.
        4. Verify that subscriber get ip from external dhcp server. successfully.
        5. Disable onu port which is being detected in voltha CLI.
        6. Repeat step 3.
        7. Verify that subscriber should not get ip from external dhcp server., and ping to gateway.
        """

    def test_subscriber_with_voltha_for_dhcpRelay_disable_enable_onu_port_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from residential subscriber to external dhcp server.
        4. Verify that subscriber get ip from external dhcp server. successfully.
        5. Disable onu port which is being detected in voltha CLI.
        6. Repeat step 3.
        7. Verify that subscriber should not get ip from external dhcp server., and ping to gateway.
        8. Enable onu port which is being detected in voltha CLI.
        9. Repeat steps 3 and 4.
        """

    def test_two_subscriber_with_voltha_for_dhcpRelay_discover(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to external dhcp server.
        4. Verify that subscribers had got different ips from external dhcp server. successfully.
        """

    def test_two_subscriber_with_voltha_for_dhcpRelay_multiple_discover(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to external dhcp server.
        4. Verify that subscribers had got ip from external dhcp server. successfully.
        5. Repeat step 3 and 4 for 10 times for both subscribers.
        6  Verify that subscribers should get same ips which are offered the first time from external dhcp server..
        """

    def test_two_subscriber_with_voltha_for_dhcpRelay_multiple_discover_for_one_subscriber(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to external dhcp server.
        4. Verify that subscribers had got ip from external dhcp server. successfully.
        5. Repeat step 3 and 4 for 10 times for only one subscriber and ping to gateway from other subscriber.
        6  Verify that subscriber should get same ip which is offered the first time from external dhcp server. and other subscriber ping to gateway should not failed
        """

    def test_two_subscriber_with_voltha_for_dhcpRelay_discover_desired_ip_address_for_one_subscriber(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from one residential subscriber to external dhcp server.
        3. Send dhcp request with desired ip from other residential subscriber to external dhcp server.
        4. Verify that subscribers had got different ips (one subscriber desired ip and other subscriber random ip) from external dhcp server. successfully.
        """

    def test_two_subscriber_with_voltha_for_dhcpRelay_discover_in_range_and_out_of_range_from_dhcp_pool_ip_addresses(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request with desired wihtin dhcp pool ip from one residential subscriber to external dhcp server.
        3. Send dhcp request with desired without in dhcp pool ip from other residential subscriber to external dhcp server.
        4. Verify that subscribers had got different ips (both subscriber got random ips within dhcp pool) from external dhcp server. successfully.
        """

    def test_two_subscriber_with_voltha_for_dhcpRelay_disable_onu_port_for_one_subscriber(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to external dhcp server.
        4. Verify that subscribers had got ip from external dhcp server. successfully.
        5. Disable onu port on which access one subscriber and ping to gateway from other subscriber.
        6. Repeat step 3 and 4 for one subscriber where uni port is down.
        7. Verify that subscriber should not get ip from external dhcp server. and other subscriber ping to gateway should not failed.
        """

    def test_two_subscriber_with_voltha_for_dhcpRelay_toggle_onu_port_for_one_subscriber(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to external dhcp server.
        4. Verify that subscribers had got ip from external dhcp server. successfully.
        5. Disable onu port on which access one subscriber and ping to gateway from other subscriber.
        6. Repeat step 3 and 4 for one subscriber where uni port is down.
        7. Verify that subscriber should not get ip from external dhcp server. and other subscriber ping to gateway should not failed.
        8. Enable onu port on which was disable at step 5 and ping to gateway from other subscriber.
        9. Repeat step 3 and 4 for one subscriber where uni port is up now.
        10. Verify that subscriber should get ip from external dhcp server. and other subscriber ping to gateway should not failed.
        """

    def test_two_subscriber_with_voltha_for_dhcpRelay_disable_olt_detected_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to external dhcp server.
        4. Verify that subscribers had got ip from external dhcp server. successfully.
        5. Start pinging continuously from one subscriber and repeat steps 3 and 4 for other subscriber.
        6. Disable the olt device which is detected in voltha.
        7. Verify that subscriber should not get ip from external dhcp server. and other subscriber ping to gateway should failed.
        """

    def test_two_subscriber_with_voltha_for_dhcpRelay_toggle_olt_detected_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to external dhcp server.
        4. Verify that subscribers had got ip from external dhcp server. successfully.
        5. Start pinging continuously from one subscriber and repeat steps 3 and 4 for other subscriber.
        6. Disable the olt device which is detected in voltha.
        7. Verify that subscriber should not get ip from external dhcp server. and other subscriber ping to gateway should failed.
        8. Enable the olt device which is detected in voltha.
        9. Verify that subscriber should get ip from external dhcp server. and other subscriber ping to gateway should not failed.
        """

    def test_two_subscriber_with_voltha_for_dhcpRelay_pause_olt_detected_in_voltha(self):
        """
        Test Method:
        0. Make sure that voltha and external dhcp server are up and running on CORD-POD setup.
        1. OLT and ONU is detected and validated.
        2. Issue  tls auth packets from CORD TESTER voltha test module acting as a subscriber..
        3. Send dhcp request from two residential subscribers to external dhcp server.
        4. Verify that subscribers had got ip from external dhcp server. successfully.
        5. Start pinging continuously from one subscriber and repeat steps 3 and 4 for other subscriber.
        6. Pause the olt device which is detected in voltha.
        7. Verify that subscriber should not get ip from external dhcp server. and other subscriber ping to gateway should failed.
        """