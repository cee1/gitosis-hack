import errno
import os
import logging
import re
from ConfigParser import NoSectionError, NoOptionError, RawConfigParser

def mkdir(*a, **kw):
    try:
        os.mkdir(*a, **kw)
    except OSError, e:
        if e.errno == errno.EEXIST:
            pass
        else:
            raise

def getRepositoryDir(config):
    repositories = os.path.expanduser('~')
    try:
        path = config.get('gitosis', 'repositories')
    except (NoSectionError, NoOptionError):
        repositories = os.path.join(repositories, 'repositories')
    else:
        repositories = os.path.join(repositories, path)
    return repositories

def getGeneratedFilesDir(config):
    try:
        generated = config.get('gitosis', 'generate-files-in')
    except (NoSectionError, NoOptionError):
        generated = os.path.expanduser('~/gitosis')
    return generated

def getSSHAuthorizedKeysPath(config):
    try:
        path = config.get('gitosis', 'ssh-authorized-keys-path')
    except (NoSectionError, NoOptionError):
        path = os.path.expanduser('~/.ssh/authorized_keys')
    return path

def _extract_reldir(topdir, dirpath):
    if topdir == dirpath:
        return '.'
    prefix = topdir + '/'
    assert dirpath.startswith(prefix)
    reldir = dirpath[len(prefix):]
    return reldir

class RepoProp(object):
    name = "Unknown"
 
    def action(self, repobase, reponame, val):
        """action for this prop"""

    def _get(self, config, section):
        try:
            val = config.get(section, self.name)
        except (NoSectionError, NoOptionError):
            val = None
        return val

    def trigger(self, config, section, repobase, reponame):
        val = self._get(config, section)
        if val != None:
            self.action(repobase, reponame, val)
    
class RepositoryDir(object):
    log = logging.getLogger('gitosis.RepositoryDir')

    def __init__(self, config, props):
        self.repositories = getRepositoryDir(config)
        self.config = config
        self.props = props

    def __collect_pattern(self):
        if hasattr(self, 'repo_patterns'):
            return

        config = self.config
        repo_patterns = {}
        for section in config.sections():
            if section.startswith('repo ') and config.has_option(section, 'path'):
                try:
                    r = re.compile(config.get(section, 'path'))
                    repo_patterns[r] = section
                except re.Error:
                    self.log.debug('Bad regex express for section %r', section)
        self.repo_patterns = repo_patterns

    def travel(self):
        repositories = self.repositories
        def _error(e):
            if e.errno == errno.ENOENT:
                pass
            else:
                raise e

        for (dirpath, dirnames, filenames) \
                in os.walk(repositories, onerror=_error):
            # oh how many times i have wished for os.walk to report
            # topdir and reldir separately, instead of dirpath
            reldir = _extract_reldir(
                topdir=repositories,
                dirpath=dirpath,
                )

            self.log.debug('Walking %r, seeing %r', reldir, dirnames)

            to_recurse = []
            repos = []
            for dirname in dirnames:
                if dirname.endswith('.git'):
                    repos.append(dirname)
                else:
                    to_recurse.append(dirname)
            dirnames[:] = to_recurse

            for repo in repos:
                name, ext = os.path.splitext(repo)
                if reldir != '.':
                    name = os.path.join(reldir, name)
                assert ext == '.git'

                self.visit_one(name)
 
    def visit_one(self, name):
        repositories = self.repositories
        config = self.config
        props = self.props

        self.__collect_pattern()

        for p in self.repo_patterns:
            if p.match(name):
                section = self.repo_patterns[p]
                break
        else:
            section = 'repo %s' % name

        for p in props:
            p.trigger(config, section, repositories, name)

