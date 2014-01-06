from fabric.api import local, env, task, puts
from fabric.colors import red


prod_env = dict(
    ansible_inventory='provisioning/production')

test_env = dict(
    ansible_inventory='provisioning/stage')


env.ansible_targets = 'all'
env.output_prefix = False


def environ(env_name='prod'):
    """Sets corresponding env variables for the further commands"""
    env_map = {
        'prod': 'prod_env',
        'test': 'test_env',
    }
    if env_name in env_map:
        env.update(globals()[env_map[env_name]])
    else:
        puts(red('Choose a valid env name: {}'.format(', '.join(env_map.keys()))))


@task
def prod():
    """Sets prod env variables"""
    environ(env_name='prod')


@task
def test():
    """Sets test env variables"""
    environ(env_name='test')


@task
def hosts(targets):
    env.ansible_targets = targets


@task
def ansible(args):
    """Proxy call for ansible"""
    local('ansible -i {ansible_inventory} {ansible_targets} {args}'.format(args=args, **env))


@task
def provision(play_book, args=''):
    """Starts provisioning"""
    shortcuts = {
        'nas': 'provisioning/nas.yml',
    }
    play_book = shortcuts.get(play_book, play_book)
    local('ansible-playbook -i {ansible_inventory} {play_book} {args}'.format(play_book=play_book, args=args, **env))


@task
def ans(alias):
    """Calls alias command"""
    shortcuts = {
        'nas': lambda: provision('nas', '-K'),

        'ping': lambda: ping(),
        'facts': lambda: ansible('-m setup'),
        'reboot': lambda: cmd('sudo /sbin/reboot'),

        'restart-dlna': lambda: ansible('-m service -a "name=minidlna state=restarted"'),
        'log-dlna': lambda: cmd('tail -n 50 /var/log/minidlna.log'),

        'restart-deluge': lambda: ansible('-m service -a "name=deluged state=restarted"'),
        'log-deluge': lambda: cmd('sudo tail -n 50 /var/log/deluge/daemon/warning.log'),
    }

    def h():
        puts('Available aliases:')
        for k in shortcuts:
            puts(' - {}'.format(k))

    shortcuts.get(alias, h)()


@task
def ping():
    """Ping all hosts via ansible"""
    ansible(env.ansible_targets, '-m ping')


@task
def cmd(command):
    """Runs commands on all remote hosts"""
    ansible('-a "{}"'.format(command))


