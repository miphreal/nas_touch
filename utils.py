import os
import tempfile

from fabric.api import run, settings, cd, local, lcd, put, sudo
from fabric.colors import green
from fabric.contrib.files import append
from fabric.utils import _AttributeDict


def log(txt):
    print(green('\n' + txt))


def log_method(func):
    def wrapper(self, *args, **kwargs):
        log(func.__name__)
        return func(self, *args, **kwargs)
    return wrapper


def chmod(f, mode=774, recursive=False):
    if mode and f:
        sudo('chmod {mode} {recursive} {file}'.format(
            mode=mode, file=f, recursive=('--recursive' if recursive else '')))


def chown(f, user, group=None, recursive=False):
    if user and f:
        sudo('chown {user}:{group} {recursive} {file}'.format(
            user=user, group=group or user, file=f, recursive=('--recursive' if recursive else '')))


def deb_install(*packages):
    if packages:
        sudo('apt-get update')
        sudo('apt-get install -y {packages}'.format(packages=' '.join(packages)))


def mkdir(path):
    sudo('mkdir -p {path}'.format(path=path))


def symlink(src, dst):
    sudo('ln -s {} {}'.format(src, dst))


def _merge(*dicts, **kwargs):
    d = kwargs
    for src_dict in dicts:
        d.update(src_dict or {})
    return d


class Format(object):
    init_kwargs = ('text:_text', 'kw:_kw', 'alias_name:_alias')
    _text = ''
    _kw = None

    shared_kw = _AttributeDict()

    def __init__(self, *args, **kwargs):
        self._kw = self._kw or {}

        for val, (arg, attr) in zip(args, self._init_kwargs()):
            kwargs[arg] = val

        self.update(check_all_init_kwargs=True, **kwargs)

        if self._alias:
            self.__class__.shared_kw[self._alias] = self

    def _init_kwargs(self):
        return map(lambda s: s.split(':'), self.init_kwargs)

    def back_map(self):
        return {arg: getattr(self, attr) for arg, attr in self._init_kwargs()}

    def clone(self, **extra):
        obj = self.__class__(**_merge(self.back_map(), extra))

        return obj

    def update(self, check_all_init_kwargs=False, **kwargs):
        old_kw = getattr(self, '_kw', {})

        self.__dict__.update({attr: kwargs.get(arg, '')
                              for arg, attr in self._init_kwargs()
                              if (arg in kwargs and getattr(self, attr, None) is None) or check_all_init_kwargs})

        self._kw = _merge(old_kw, self.back_map(), self._kw)

        return self

    def format_kw(self, **kwargs):
        return _merge(self._kw, kwargs, alias=self.shared_kw)

    def format(self, *args, **kwargs):
        return self.text(**kwargs)

    __format__ = lambda self, *args, **kwargs: format(unicode(self), *args, **kwargs)

    def text(self, text=None, **kwargs):
        return (text or self._text).format(**self.format_kw(**kwargs))

    def __unicode__(self):
        return self.text()

    def __str__(self):
        return self.text()

    def __add__(self, other):
        return unicode(self) + other


class AddUserCmd(Format):
    init_kwargs = ('user:_user', 'password:_password',
                   'groups:_groups', 'extra_opts:_extra_opts',) + Format.init_kwargs[1:]
    _text = 'useradd --create-home --user-group {groups_opts} {extra_opts} --password \'{password}\' {user}'

    def text(self, text=None, **kwargs):
        kwargs['groups_opts'] = ('--groups ' + ','.join(self._groups)) if self._groups else ''
        return super(AddUserCmd, self).text(text, **kwargs)


class File(Format):
    init_kwargs = ('file_name:_text', 'user:_user', 'group:_group', 'mode:_chmod',) + Format.init_kwargs[1:]

    def path(self, path=None, **kwargs):
        return self.text(path, **kwargs)


class TemplateFile(File):

    def text(self, text=None, **kwargs):
        template_file = super(TemplateFile, self).text(text=text, **kwargs)

        if text is None:
            fd, path = tempfile.mkstemp()
            with os.fdopen(fd, 'w') as f, open(template_file) as f_src:
                f.write(f_src.read().format(**self.format_kw()))
            return path

        return template_file


class Dir(File):
    init_kwargs = ('dir_name:_text',) + File.init_kwargs[1:]

    def mkdir(self):
        path = self.path()
        mkdir(path)
        chown(path, user=self._user, group=self._group, recursive=True)
        chmod(path, mode=self._chmod, recursive=True)


class SyncFile(File):
    init_kwargs = ('local_file:_text', 'nas_file:_dst') + File.init_kwargs[1:]

    def put(self, use_sudo=True, **kwargs):
        src, dst = self.path(), self.path(self._dst)
        print repr(self)
        print 'put', src, dst
        put(src, dst, use_sudo=use_sudo, **kwargs)
        chown(dst, self._user, self._group)
        chmod(dst, self._chmod)


class TemplateSyncFile(TemplateFile, SyncFile):
    pass


class Symlink(File):
    init_kwargs = ('file_name:_text', 'link:_link') + File.init_kwargs[1:]

    def symlink(self, use_sudo=True, **kwargs):
        src, dst = self.path(), self.path(self._link)
        symlink(src, dst)

    def unlink(self):
        with settings(warn_only=True):
            sudo('rm {link}'.format(link=self.path(self._link)))


class Package(object):
    name = 'package_name'
    job_name = None

    class INIT_SYSTEM:
        SYSTEM_V = 'service {pkg.job_name} {action}'
        UPSTART = '{action} {pkg.job_name}'

    init_system_type = INIT_SYSTEM.SYSTEM_V

    package_dirs = []
    package_symlinks = []
    package_logs = []
    config_files = []

    add_users = [] # list of adduser commands
    user = group = 'nobody'
    groups = []

    deb_ppa = []
    deb_packages = []

    conf_dir = Dir('{env.project_path}/conf/nas/{pkg.name}')

    def __init__(self, env):
        self.env = env
        self._update_formated_strings()

    def _update_formated_strings(self):
        def upd(value):
            if isinstance(value, Format):
                value.update(kw=self.kw(), **self._instance_options())
            return value

        for k, v in self._instance_options().items():
            if isinstance(v, (tuple, list)):
                v = map(upd, v)
            setattr(self, k, upd(v))

    def _instance_options(self):
        keys = filter(lambda key: not key.startswith('_') and not callable(getattr(self, key)), dir(self))
        return dict(zip(keys, map(lambda key: getattr(self, key), keys)))

    def kw(self, **kwargs):
        return dict(kwargs, pkg=self, env=self.env)

    def format(self, text, **kwargs):
        kw = self.kw(**kwargs)

        if isinstance(text, Format):
            text.update(kw=kw, **self._instance_options())

        return text.format(alias_name=Format.shared_kw, **kw)

    @log_method
    def install_deb_packages(self):
        for repo in self.deb_ppa:
            sudo(self.format('add-apt-repository -y {repo}', repo=repo))

        deb_install(*self.deb_packages)

    @log_method
    def init_users(self):
        for cmd in map(self.format, self.add_users):
            with settings(warn_only=True):
                sudo(cmd)

    @log_method
    def init_package_dirs(self):
        for path in self.package_dirs:
            path.mkdir()

    @log_method
    def init_package_symlinks(self):
        for path in self.package_symlinks:
            path.symlink()

    @log_method
    def destroy_package_symlinks(self):
        for path in self.package_symlinks:
            path.unlink()

    @log_method
    def init_config_files(self):
        for cfg_file in self.config_files:
            cfg_file.put()

    @log_method
    def bind_groups(self):
        for group in self.groups:
            with settings(warn_only=True):
                sudo(self.format('adduser {pkg.user} {existed_group}', existed_group=group))

    def show_logs(self):
        for log_file in map(self.format, self.package_logs):
            log('Log file: {}'.format(log_file))
            sudo('tail -n20 {}'.format(log_file))

    def install(self):
        log(self.format('=== INSTALL {pkg.name} ==='))

        self.stop()
        self.destroy_package_symlinks()

        self.pre_install()
        self.install_deb_packages()
        self.init_users()
        self.init_package_dirs()
        self.init_config_files()
        self.setup_package()
        self.init_package_symlinks()
        self.bind_groups()
        self.post_install()

        self.start()
        self.show_logs()

    def start(self):
        if self.job_name:
            with settings(warn_only=True):
                sudo(self.format(self.init_system_type, action='start'))

    def stop(self):
        if self.job_name:
            with settings(warn_only=True):
                sudo(self.format(self.init_system_type, action='stop'))

    def restart(self):
        self.stop()
        self.start()

    def pre_install(self):
        pass

    def post_install(self):
        pass

    def setup_package(self):
        pass


class NAS(Package):
    name = 'NAS'

    package_dirs = [
        Dir('/mnt/data', user='nas-user', group='nas-user', mode=775, alias_name='nas_data_dir'),
        Dir('{alias.nas_data_dir}/public', user='nas-public', group='nas-public', mode=777),
        Dir('{alias.nas_data_dir}/public/torrents', user='nas-public', group='nas-public', mode=777),

        Dir('{alias.nas_data_dir}/music', user='nas-user', group='nas-user', mode=775),
        Dir('{alias.nas_data_dir}/audiobooks', user='nas-user', group='nas-user', mode=775),
        Dir('{alias.nas_data_dir}/video', user='nas-user', group='nas-user', mode=775),
        Dir('{alias.nas_data_dir}/pictures', user='nas-user', group='nas-user', mode=775),
        Dir('{alias.nas_data_dir}/install', user='nas-user', group='nas-user', mode=775),
        Dir('{alias.nas_data_dir}/books', user='nas-user', group='nas-user', mode=775),

        Dir('{alias.nas_data_dir}/.incomplete', user='nas-user', group='nas-user', mode=777),
        Dir('{alias.nas_data_dir}/.daemons', user='nas-user', group='nas-user', mode=777),
    ]

    add_users = [
        AddUserCmd('nas-public', 'nas-public'),
        AddUserCmd('nas-user', 'nas-user%)', ['nas-public']),
        AddUserCmd('nas-admin', 'nas-admin%)ok', ['nas-public', 'nas-user', 'sudo'], '--system'),
    ]
    user = group = 'nas-admin'

    def pre_install(self):
        with settings(warn_only=True):
            log('=== MOUNT fs ===')
            sudo('mount /dev/mapper/nas-data /mnt/data')

    def setup_package(self):
        append('/etc/sudoers', 'nas-admin ALL=(ALL) NOPASSWD: ALL', use_sudo=True)

        map(sudo, [
            'locale-gen ru_RU.UTF-8',
            'locale-gen ru_RU',
            'update-locale',
            'dpkg-reconfigure locales',
            ])


class DLNA(Package):
    name = 'minidlna'
    job_name = 'minidlna'

    package_dirs = [
        Dir('/var/cache/minidlna')
    ]

    package_logs = [
        File('/var/log/minidlna.log')
    ]

    config_files = [
        SyncFile('{pkg.conf_dir}/{pkg.name}',      '/etc/default/minidlna'),
        SyncFile('{pkg.conf_dir}/{pkg.name}.conf', '/etc/minidlna.conf'),
    ]

    user = group = 'minidlna'
    groups = ['nas-user', 'nas-public']

    deb_ppa = ['ppa:stedy6/stedy-minidna']
    deb_packages = ['apache2', 'minidlna']

    def post_install(self):
        append('/etc/sysctl.conf', 'fs.inotify.max_user_watches = 100000', use_sudo=True)
        log('minidlna started on http://nas:8200')


class Dropbox(Package):
    name = 'dropbox'
    job_name = 'dropboxd'

    dropbox_client_link = File('https://www.dropbox.com/download?dl=packages/dropbox.py')
    dropbox_daemon_link = File('https://www.dropbox.com/download?plat=lnx.x86')

    init_system_type = Package.INIT_SYSTEM.UPSTART

    package_dirs = [
        Dir('/var/lib/{pkg.name}', mode=775, alias_name='dropboxd_dir'),
        Dir('/var/log/{pkg.name}', alias_name='dropboxd_log_dir'),
        Dir('{alias.dropboxd_dir}/.dropbox', mode=775, alias_name='dropbox_conf_dir'),
        Dir('/mnt/data/.daemons/{pkg.name}/Dropbox', alias_name='dropbox_dir'),
    ]

    package_symlinks = [
        Symlink('{alias.dropboxd_dir}/dropbox.py', '/usr/bin/dropbox'),
        Symlink('{alias.dropboxd_dir}/.dropbox-dist/dropboxd', '/usr/bin/dropboxd'),
        Symlink('{alias.dropbox_dir}', '/home/{pkg.user}/Dropbox'),
        Symlink('{alias.dropbox_conf_dir}', '/home/{pkg.user}/.dropbox'),
    ]

    package_logs = [
        File('{alias.dropboxd_log_dir}/daemon.log', alias_name='dropboxd_log')
    ]

    config_files = [
        SyncFile('{pkg.conf_dir}/{pkg.name}d.conf', '/etc/init/{pkg.job_name}.conf'),
    ]

    user = group = 'nas-user'

    def setup_package(self):
        sudo(self.format('wget {pkg.dropbox_client_link} -O {alias.dropboxd_dir}/dropbox.py'))
        with cd(self.format('{alias.dropboxd_dir}')):
            sudo(self.format('wget -O - "{pkg.dropbox_daemon_link}" | tar xzf -'))


class BitTorrent(Package):
    name = 'deluge'
    job_name = 'deluged'

    init_system_type = Package.INIT_SYSTEM.UPSTART

    deb_ppa = ['ppa:deluge-team/ppa']
    deb_packages = ['deluged', 'deluge-webui']

    package_dirs = [
        Dir('/var/lib/{pkg.name}', mode=775, alias_name='deluged_dir'),
        Dir('/var/log/{pkg.name}', mode=750, alias_name='deluged_log_dir'),
        Dir('/mnt/data/.daemons/dropbox/Dropbox/sys/nas/new-torrents', mode=777),
    ]

    package_logs = [
        File('{alias.deluged_log_dir}/daemon.log', alias_name='deluged_log'),
        File('{alias.deluged_log_dir}/web.log', alias_name='deluge_web_log'),
    ]

    config_files = [
        TemplateSyncFile('{pkg.conf_dir}/{pkg.name}d.conf', '/etc/init/{pkg.job_name}.conf'),
        SyncFile('{pkg.conf_dir}/{pkg.name}-web.conf', '/etc/init/deluge-web.conf'),
        SyncFile('{pkg.conf_dir}/log-rotate', '/etc/logrotate.d/deluge'),
        SyncFile('{pkg.conf_dir}/auth', '{alias.deluged_dir}/deluge'),
        SyncFile('{pkg.conf_dir}/web.conf', '{alias.deluged_dir}/web.conf'),
        SyncFile('{pkg.conf_dir}/core.conf', '{alias.deluged_dir}/core.conf'),
    ]

    add_users = [
        'adduser --system --group --home {alias.deluged_dir} {pkg.user}'
    ]
    user = group = 'deluge'
    groups = ['nas-user', 'nas-public']

    def post_install(self):
        log('DELUGE WEBUI - DEFAULT PASSWORD: "nas-user%)"')
        log('deluge-web started on http://nas:8112')


class BitSync(Package):
    name = 'btsync'
    job_name = 'btsyncd'

    init_system_type = Package.INIT_SYSTEM.UPSTART

    btsync_daemon_link = File('http://btsync.s3-website-us-east-1.amazonaws.com/btsync_i386.tar.gz')

    package_dirs = [
        Dir('/var/lib/{pkg.name}', mode=775, alias_name='btsyncd_dir'),
        Dir('/var/log/{pkg.name}', mode=750, alias_name='btsyncd_log_dir'),
    ]

    package_symlinks = [
        Symlink('{alias.btsyncd_dir}/btsync', '/usr/bin/btsync'),
    ]

    package_logs = [
        File('{alias.btsyncd_log_dir}/daemon.log', alias_name='btsyncd_log'),
    ]

    config_files = [
        SyncFile('{pkg.conf_dir}/{pkg.name}.conf', '{alias.btsyncd_dir}/{pkg.name}.conf'),
        SyncFile('{pkg.conf_dir}/{pkg.name}d.conf', '/etc/init/{pkg.job_name}.conf'),
    ]

    user = group = 'nas-user'

    def setup_package(self):
        with cd(self.format('{alias.btsyncd_dir}')):
            sudo('wget {pkg.btsync_daemon_link} -O dist.tar.gz')
            sudo('tar -xf dist.tar.gz')

    def post_install(self):
        log('btsync started on http://nas:8121')