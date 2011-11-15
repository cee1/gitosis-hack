import errno
import logging
import os
from ConfigParser import NoSectionError, NoOptionError

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

    def _get(self, config, section):
        if not hasattr(self, 'default_value'):
            try:
                val = config.getboolean('gitosis', self.name)
            except (NoSectionError, NoOptionError):
                val = False
            self.default_value = val

            log.debug(
                'Global default is %r',
                {True: 'allow', False: 'deny'}.get(val),
            )

        try:
            val = config.getboolean(section, self.name)
        except (NoSectionError, NoOptionError):
            val = self.default_value
        return val

    def action(self, repobase, reponame, enable):
        path = os.path.join(repobase, reponame + '.git')
        if enable:
            log.debug('Allow %r', path)
            allow_export(path)
        else:
            log.debug('Deny %r', path)
            deny_export(path)
