"""
Generate ``gitweb`` project list based on ``gitosis.conf``.

To plug this into ``gitweb``, you have two choices.

- The global way, edit ``/etc/gitweb.conf`` to say::

	$projects_list = "/path/to/your/projects.list";

  Note that there can be only one such use of gitweb.

- The local way, create a new config file::

	do "/etc/gitweb.conf" if -e "/etc/gitweb.conf";
	$projects_list = "/path/to/your/projects.list";
        # see ``repositories`` in the ``gitosis`` section
        # of ``~/.gitosis.conf``; usually ``~/repositories``
        # but you need to expand the tilde here
	$projectroot = "/path/to/your/repositories";

   Then in your web server, set environment variable ``GITWEB_CONFIG``
   to point to this file.

   This way allows you have multiple separate uses of ``gitweb``, and
   isolates the changes a bit more nicely. Recommended.
"""

import os, logging
import fcntl
import re

from ConfigParser import NoSectionError, NoOptionError

log = logging.getLogger('gitosis.gitweb')
from gitosis import util

def _escape_filename(s):
    s = s.replace('\\', '\\\\')
    s = s.replace('$', '\\$')
    s = s.replace('"', '\\"')
    return s

_repos_allow = []
_repos_disallow = []

class ProjectList(object):
    log = logging.getLogger('gitosis.gitweb.ProjectList')

    def __init__(self, path):
        self.plist_path = path
        self.__lock = None

    def lock(self):
        lk_path = self.plist_path + '.lock'
        log = self.log

        log.debug('Locking: %r', lk_path)
        if self.__lock:
            log.debug('Already Locked: %r', lk_path)
            return

        self.__lock = file(lk_path, 'w')
        fcntl.flock(self.__lock.fileno(), fcntl.LOCK_EX)

        log.debug('Locked: %r', lk_path)
        return

    def unlock(self):
        lk_path = self.plist_path + '.lock'
        log = self.log

        log.debug('UnLock: %r', lk_path)
        if not self.__lock:
            log.debug('Not Locked: %r', lk_path)
            return
        
        self.__lock.close()
        self.__lock = None

    def refresh(self):
        tmp = self.plist_path + '.tmp'

        self.lock()
        f = file(tmp, 'w')

        try:
            if _repos_allow:
                f.write('\n'.join(_repos_allow))
        except:
            f.close()
            os.remove(tmp)
            self.unlock()

            raise
        else:
            f.close()
            os.rename(tmp, self.plist_path)
            self.unlock()
    
    def update(self):
        tmp = self.plist_path + '.tmp'

        self.lock()
        f = file(tmp, 'w')

        try:
            pj_list = file(self.plist_path, 'r')
        except IOError:
            pj_list = []

        try:
            for l in pj_list:
                _l = l.strip()
                if _l and _l not in _repos_disallow:
                    f.write(l)
                    if _l in _repos_allow:
                        _repos_allow.remove(_l)

            if _repos_allow:
                f.write('\n')
                f.write('\n'.join(_repos_allow))
        except:
            f.close()
            os.remove(tmp)
            self.unlock()

            raise
        else:
            f.close()
            os.rename(tmp, self.plist_path)
            self.unlock()


class GitwebProp(util.RepoProp):
    name = "gitweb"

    def __init__(self):
        global _repos_allow, _repos_disallow
        _repos_allow = []
        _repos_disallow = []

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
        repopath = reponame + '.git'
        if enable:
            log.debug('Allow %r', repopath)
            _repos_allow.append(repopath)
        else:
            _repos_disallow.append(repopath)
            log.debug('Deny %r', repopath)

class DescriptionProp(util.RepoProp):
    name = 'description'

    def action(self, repobase, reponame, description):
        path = os.path.join(
            repobase,
            reponame + '.git',
            'description',
            )
        tmp = '%s.%d.tmp' % (path, os.getpid())
        f = file(tmp, 'w')
        try:
            print >>f, description
        finally:
            f.close()
        os.rename(tmp, path)

class OwnerProp(util.RepoProp):
    name = 'owner'

    def action(self, repobase, reponame, owner):
        path = os.path.join(
            repobase,
            reponame + '.git',
            'config',
            )

        _r_sec = re.compile('\s*\[[^\]]*\]')
        _r_owner = re.compile('\s*owner\s?=')

        gitcfg = open(path, 'r')

        tmp = '%s.%d.tmp' % (path, os.getpid())
        f = file(tmp, 'w')

        try:
            for l in gitcfg:
                f.write(l)
                if l.strip() == '[gitweb]':
                    break
            else:
                f.write('[gitweb]\n')

            for l in gitcfg:
                if _r_sec.match(l):
                    f.write('\towner = %s\n' % owner)
                    f.write(l)
                    break
                elif _r_owner.match(l):
                    f.write('\towner = %s\n' % owner)
                    break
            else:
                f.write('\towner = %s\n' % owner)

            for l in gitcfg:
                f.write(l)
        finally:
            f.close()
        os.rename(tmp, path)
