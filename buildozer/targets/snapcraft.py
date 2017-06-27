'''
Android target, based on python-for-android project (old toolchain)
'''
# ggggg
# Android target
# Thanks for Renpy (again) for its install_sdk.py and plat.py in the PGS4A
# project!
#

import sys
if sys.platform == 'win32':
    raise NotImplementedError('Windows platform not yet working for Android')

ANDROID_API = '19'
ANDROID_MINAPI = '9'
ANDROID_SDK_VERSION = '20'
ANDROID_NDK_VERSION = '9c'
APACHE_ANT_VERSION = '1.9.4'

import traceback
import os
import io
import re
import ast
from pipes import quote
from sys import platform, executable
from buildozer import BuildozerException
from buildozer import IS_PY3
from buildozer.target import Target
from os import environ
from os.path import exists, join, realpath, expanduser, basename, relpath
from platform import architecture
from shutil import copyfile
from glob import glob

from buildozer.libs.version import parse


class TargetSnapcraft(Target):
    targetname = 'snapcraft'
    p4a_apk_cmd = "python build.py"

    @property
    def android_sdk_version(self):
        return self.buildozer.config.getdefault('app', 'android.sdk',
                                                ANDROID_SDK_VERSION)

    @property
    def android_api(self):
        return self.buildozer.config.getdefault('app', 'android.api',
                                                ANDROID_API)

    @property
    def android_minapi(self):
        return self.buildozer.config.getdefault('app', 'android.minapi',
                                                ANDROID_MINAPI)

    @property
    def android_sdk_dir(self):
        directory = expanduser(self.buildozer.config.getdefault(
            'app', 'android.sdk_path', ''))
        if directory:
            return realpath(directory)
        version = self.buildozer.config.getdefault('app', 'android.sdk',
                                                   self.android_sdk_version)
        return join(self.buildozer.global_platform_dir,
                    'android-sdk-{0}'.format(version))

    @property
    def apache_ant_dir(self):
        directory = expanduser(self.buildozer.config.getdefault(
            'app', 'android.ant_path', ''))
        if directory:
            return realpath(directory)
        version = self.buildozer.config.getdefault('app', 'android.ant',
                                                   APACHE_ANT_VERSION)
        return join(self.buildozer.global_platform_dir,
                    'apache-ant-{0}'.format(version))

    def check_requirements(self):
        if platform in ('darwin', ):
            self.android_cmd = join(self.android_sdk_dir, 'tools', 'android')
            self.adb_cmd = join(self.android_sdk_dir, 'platform-tools', 'adb')
        else:
            self.android_cmd = join(self.android_sdk_dir, 'tools', 'android')
            self.adb_cmd = join(self.android_sdk_dir, 'platform-tools', 'adb')

            # Check for C header <zlib.h>.
            _, _, returncode_dpkg = self.buildozer.cmd('dpkg --version',
                                                       break_on_error=False)
            is_debian_like = (returncode_dpkg == 0)
            if is_debian_like and \
                not self.buildozer.file_exists('/usr/include/zlib.h'):
                raise BuildozerException(
                    'zlib headers must be installed, '
                    'run: sudo apt-get install zlib1g-dev')

        # Need to add internally installed ant to path for external tools
        # like adb to use
        path = [join(self.apache_ant_dir, 'bin')]
        if 'PATH' in self.buildozer.environ:
            path.append(self.buildozer.environ['PATH'])
        else:
            path.append(os.environ['PATH'])
        self.buildozer.environ['PATH'] = ':'.join(path)
        checkbin = self.buildozer.checkbin
        checkbin('Git (git)', 'git')
        checkbin('Cython (cython)', 'cython')

    def check_configuration_tokens(self):
        errors = []

        # check the permission
        available_permissions = self._get_available_permissions()
        if available_permissions:
            permissions = self.buildozer.config.getlist(
                'app', 'android.permissions', [])
            for permission in permissions:
                # no check on full named permission
                # like com.google.android.providers.gsf.permission.READ_GSERVICES
                if '.' in permission:
                    continue
                permission = permission.upper()
                if permission not in available_permissions:
                    errors.append(
                        '[app] "android.permission" contain an unknown'
                        ' permission {0}'.format(permission))

        super(TargetSnapcraft, self).check_configuration_tokens(errors)

    def _get_available_permissions(self):
        key = 'android:available_permissions'
        key_sdk = 'android:available_permissions_sdk'

        refresh_permissions = False
        sdk = self.buildozer.state.get(key_sdk, None)
        if not sdk or sdk != self.android_sdk_version:
            refresh_permissions = True
        if key not in self.buildozer.state:
            refresh_permissions = True
        if not refresh_permissions:
            return self.buildozer.state[key]

        try:
            self.buildozer.debug(
                'Read available permissions from api-versions.xml')
            import xml.etree.ElementTree as ET
            fn = join(self.android_sdk_dir, 'platform-tools', 'api',
                      'api-versions.xml')
            with io.open(fn, encoding='utf-8') as fd:
                doc = ET.fromstring(fd.read())
            fields = doc.findall(
                './/class[@name="android/Manifest$permission"]/field[@name]')
            available_permissions = [x.attrib['name'] for x in fields]

            self.buildozer.state[key] = available_permissions
            self.buildozer.state[key_sdk] = self.android_sdk_version
            return available_permissions
        except:
            return None

    def install_platform(self):
        #install what needed for the platform (android, ios, osx or linux) in this case for linux (snapcraft)

        # ultimate configuration check.
        # some of our configuration cannot be check without platform.
        self.check_configuration_tokens()

        self.buildozer.environ.update({
            'PACKAGES_PATH': self.buildozer.global_packages_dir,
        })

    def _get_package(self):
        config = self.buildozer.config
        package_domain = config.getdefault('app', 'package.domain', '')
        package = config.get('app', 'package.name')
        if package_domain:
            package = package_domain + '.' + package
        return package.lower()

    def get_dist_dir(self, dist_name):
        return join(self.pa_dir, 'dist', dist_name)

    @property
    def dist_dir(self):
        dist_name = self.buildozer.config.get('app', 'package.name')
        return self.get_dist_dir(dist_name)

    def execute_build_package(self, build_cmd):
        dist_name = self.buildozer.config.get('app', 'package.name')
        cmd = [self.p4a_apk_cmd]
        for args in build_cmd:
            cmd.append(" ".join(args))
        cmd = " ".join(cmd)
        self.buildozer.cmd(cmd, cwd=self.get_dist_dir(dist_name))

    def build_package(self):
        dist_name = self.buildozer.config.get('app', 'package.name')
        dist_dir = self.get_dist_dir(dist_name)
        config = self.buildozer.config
        package = self._get_package()
        version = self.buildozer.get_version()

        # add extra libs/armeabi files in dist/default/libs/armeabi
        # (same for armeabi-v7a, x86, mips)
        for config_key, lib_dir in (
            ('android.add_libs_armeabi', 'armeabi'),
            ('android.add_libs_armeabi_v7a', 'armeabi-v7a'),
            ('android.add_libs_x86', 'x86'),
            ('android.add_libs_mips', 'mips')):

            patterns = config.getlist('app', config_key, [])
            if not patterns:
                continue

            self.buildozer.debug('Search and copy libs for {}'.format(lib_dir))
            for fn in self.buildozer.file_matches(patterns):
                self.buildozer.file_copy(
                    join(self.buildozer.root_dir, fn),
                    join(dist_dir, 'libs', lib_dir, basename(fn)))

        # build the app
        build_cmd = [
            ("--name", quote(config.get('app', 'title'))),
            ("--version", version),
            ("--package", package),
            ("--sdk", config.getdefault('app', 'android.api',
                                        self.android_api)),
            ("--minsdk", config.getdefault('app', 'android.minapi',
                                           self.android_minapi)),
        ]
        is_private_storage = config.getbooldefault(
            'app', 'android.private_storage', True)
        if is_private_storage:
            build_cmd += [("--private", self.buildozer.app_dir)]
        else:
            build_cmd += [("--dir", self.buildozer.app_dir)]

        # add permissions
        permissions = config.getlist('app', 'android.permissions', [])
        for permission in permissions:
            # force the latest component to be uppercase
            permission = permission.split('.')
            permission[-1] = permission[-1].upper()
            permission = '.'.join(permission)
            build_cmd += [("--permission", permission)]

        # meta-data
        meta_datas = config.getlistvalues('app', 'android.meta_data', [])
        for meta in meta_datas:
            key, value = meta.split('=', 1)
            meta = '{}={}'.format(key.strip(), value.strip())
            build_cmd += [("--meta-data", meta)]

        # add extra Java jar files
        add_jars = config.getlist('app', 'android.add_jars', [])
        for pattern in add_jars:
            pattern = join(self.buildozer.root_dir, pattern)
            matches = glob(expanduser(pattern.strip()))
            if matches:
                for jar in matches:
                    build_cmd += [("--add-jar", jar)]
            else:
                raise SystemError('Failed to find jar file: {}'.format(
                    pattern))

        # add presplash
        presplash = config.getdefault('app', 'presplash.filename', '')
        if presplash:
            build_cmd += [("--presplash", join(self.buildozer.root_dir,
                                               presplash))]

        # add icon
        icon = config.getdefault('app', 'icon.filename', '')
        if icon:
            build_cmd += [("--icon", join(self.buildozer.root_dir, icon))]

        # OUYA Console support
        ouya_category = config.getdefault('app', 'android.ouya.category',
                                          '').upper()
        if ouya_category:
            if ouya_category not in ('GAME', 'APP'):
                raise SystemError(
                    'Invalid android.ouya.category: "{}" must be one of GAME or APP'.format(
                        ouya_category))
            # add icon
            ouya_icon = config.getdefault('app', 'android.ouya.icon.filename',
                                          '')
            build_cmd += [("--ouya-category", ouya_category)]
            build_cmd += [("--ouya-icon", join(self.buildozer.root_dir,
                                               ouya_icon))]

        # add orientation
        orientation = config.getdefault('app', 'orientation', 'landscape')
        if orientation == 'all':
            orientation = 'sensor'
        build_cmd += [("--orientation", orientation)]

        # fullscreen ?
        fullscreen = config.getbooldefault('app', 'fullscreen', True)
        if not fullscreen:
            build_cmd += [("--window", )]

        # wakelock ?
        wakelock = config.getbooldefault('app', 'android.wakelock', False)
        if wakelock:
            build_cmd += [("--wakelock", )]

        # intent filters
        intent_filters = config.getdefault(
            'app', 'android.manifest.intent_filters', '')
        if intent_filters:
            build_cmd += [("--intent-filters", join(self.buildozer.root_dir,
                                                    intent_filters))]

        # build only in debug right now.
        if self.build_mode == 'debug':
            build_cmd += [("debug", )]
            mode = 'debug'
        else:
            build_cmd += [("release", )]
            mode = 'release'

        self.execute_build_package(build_cmd)

        try:
            self.buildozer.hook("android_pre_build_apk")
            self.execute_build_package(build_cmd)
            self.buildozer.hook("android_post_build_apk")
        except:
            # maybe the hook fail because the apk is not
            pass

        # XXX found how the apk name is really built from the title
        if exists(join(dist_dir, "build.gradle")):
            # on gradle build, the apk use the package name, and have no version
            packagename = config.get('app', 'package.name')
            apk = u'{packagename}-{mode}.apk'.format(
                packagename=packagename, mode=mode)
            apk_dir = join(dist_dir, "build", "outputs", "apk")
            apk_dest = u'{packagename}-{version}-{mode}.apk'.format(
                packagename=packagename, mode=mode, version=version)

        else:
            # on ant, the apk use the title, and have version
            bl = u'\'" ,'
            apptitle = config.get('app', 'title')
            if hasattr(apptitle, 'decode'):
                apptitle = apptitle.decode('utf-8')
            apktitle = ''.join([x for x in apptitle if x not in bl])
            apk = u'{title}-{version}-{mode}.apk'.format(
                title=apktitle,
                version=version,
                mode=mode)
            apk_dir = join(dist_dir, "bin")
            apk_dest = apk

        # copy to our place
        copyfile(join(apk_dir, apk), join(self.buildozer.bin_dir, apk_dest))

        self.buildozer.info('Android packaging done!')
        self.buildozer.info(
            u'APK {0} available in the bin directory'.format(apk_dest))
        self.buildozer.state['android:latestapk'] = apk_dest
        self.buildozer.state['android:latestmode'] = self.build_mode

    @property
    def serials(self):
        if hasattr(self, '_serials'):
            return self._serials
        serial = environ.get('ANDROID_SERIAL')
        if serial:
            return serial.split(',')
        l = self.buildozer.cmd('{} devices'.format(self.adb_cmd),
                               get_stdout=True)[0].splitlines()
        serials = []
        for serial in l:
            if not serial:
                continue
            if serial.startswith('*') or serial.startswith('List '):
                continue
            serials.append(serial.split()[0])
        self._serials = serials
        return serials

    def cmd_deploy(self, *args):
        super(TargetSnapcraft, self).cmd_deploy(*args)
        state = self.buildozer.state
        if 'android:latestapk' not in state:
            self.buildozer.error('No APK built yet. Run "debug" first.')

        if state.get('android:latestmode', '') != 'debug':
            self.buildozer.error('Only debug APK are supported for deploy')

        # search the APK in the bin dir
        apk = state['android:latestapk']
        full_apk = join(self.buildozer.bin_dir, apk)
        if not self.buildozer.file_exists(full_apk):
            self.buildozer.error(
                'Unable to found the latest APK. Please run "debug" again.')

        # push on the device
        for serial in self.serials:
            self.buildozer.environ['ANDROID_SERIAL'] = serial
            self.buildozer.info('Deploy on {}'.format(serial))
            self.buildozer.cmd('{0} install -r "{1}"'.format(
                               self.adb_cmd, full_apk),
                               cwd=self.buildozer.global_platform_dir)
        self.buildozer.environ.pop('ANDROID_SERIAL', None)

        self.buildozer.info('Application pushed.')

    def cmd_run(self, *args):
        super(TargetSnapcraft, self).cmd_run(*args)

        entrypoint = self.buildozer.config.getdefault(
            'app', 'android.entrypoint', 'org.renpy.android.PythonActivity')
        package = self._get_package()

        # push on the device
        for serial in self.serials:
            self.buildozer.environ['ANDROID_SERIAL'] = serial
            self.buildozer.info('Run on {}'.format(serial))
            self.buildozer.cmd(
                '{adb} shell am start -n {package}/{entry} -a {entry}'.format(
                    adb=self.adb_cmd,
                    package=package,
                    entry=entrypoint),
                cwd=self.buildozer.global_platform_dir)
        self.buildozer.environ.pop('ANDROID_SERIAL', None)

        self.buildozer.info('Application started.')


def get_target(buildozer):
    return TargetSnapcraft(buildozer)
