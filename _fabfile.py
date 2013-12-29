import os
from fabric.api import env, run, local, put, sudo
from fabric.contrib.files import uncomment

# === UTILS ===
from utils import log
import utils


path = os.path.join


# === CONFIGS ===
env.hosts = ['nas-admin@nas:22']

#ssh
env.user = 'nas-admin'
env.password = 'nas-admin%)ok'
env.project_path = '/code/nas_touch'
env.nas_admin_ssh_key = '%(project_path)s/conf/nas/id_nas' % env
env.key_filename = [env.nas_admin_ssh_key]


def install_ssh_key():
    """
    Delegate ssh file to server.
    Initial start like the command bellow:
        fab nas_install_ssh_key -u nas-admin -p 'nas-admin%)ok'
    All next command we can run in the simple format:
        fab command
    """
    log('=== INSTALL sshd key file ===')
    run('mkdir -p ~/.ssh')
    run('touch ~/.ssh/authorized_keys')
    put('%(project_path)s/conf/nas/id_nas.pub' % env, '~/.ssh/authorized_keys', mode=0600)
    uncomment('/etc/ssh/sshd_config', '.AuthorizedKeysFile.*', use_sudo=True)
    sudo('service ssh restart')


def ssh():
    log('=== CONNECTING to NAS ===')
    local('chmod 400 %s' % env.nas_admin_ssh_key)
    local('ssh %(host)s -i %(key)s' % {'host': env.hosts[0].rpartition(':')[0],
                                       'key': env.nas_admin_ssh_key})


def nas_install():
    install_log()
    install_samba()


env.nas_software = [
    utils.NAS,
    utils.DLNA,
    utils.Dropbox,
    utils.BitTorrent,
    utils.BitSync,
]


def nas_test_install():
    for package in env.nas_software:
        package(env=env).install()


nas_install = nas_test_install

__all__ = ['install_ssh_key', 'ssh', 'nas_install']
