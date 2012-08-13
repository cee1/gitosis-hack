import errno
import logging
import os
from gitosis.gitoliteConfig import GitoliteConfigException

log = logging.getLogger('gitosis.gitdaemon')
from gitosis import util

def export_ok_path(repopath):
    p = os.path.join(repopath, 'git-daemon-export-ok')
    return p

def allow_export(repopath):
    p = export_ok_path(repopath)
    file(p, 'a').close()

def deny_export(repopath):
    p = export_ok_path(repopath)
    try:
        os.unlink(p)
    except OSError, e:
        if e.errno == errno.ENOENT:
            pass
        else:
            raise

class DaemonProp(util.RepoProp):
    name = "daemon"

    def _get(self, config, reponame):
        try:
            users = config.get_repo(reponame, 'R')
        except GitoliteConfigException:
            log.exception('Failed to get users that can read(Only) repo \'%s\'' % reponame)
            return

        if users and 'daemon' in users:
            return True

        return False

    def action(self, repobase, name, reponame, enable):
        path = os.path.join(repobase, name + '.git')
        if enable:
            log.debug('Allow %r', path)
            allow_export(path)
        else:
            log.debug('Deny %r', path)
            deny_export(path)
