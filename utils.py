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
