import errno
import os
import logging
import re
from gitosis.gitoliteConfig import GitoliteConfigException
from base64 import urlsafe_b64decode

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

    path = config.get_gitosis('repositories')
    if path == None:
        repositories = os.path.join(repositories, 'repositories')
    else:
        repositories = os.path.join(repositories, path)
    return repositories

def getGeneratedFilesDir(config):
    generated = config.get_gitosis('generate-files-in')
    if generated == None:
        generated = os.path.expanduser('~/gitosis')
    return generated

def getSSHAuthorizedKeysPath(config):
    path = config.get_gitosis('ssh-authorized-keys-path')
    if path == None:
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
 
    def action(self, repobase, name, reponame, val):
        """action for this prop"""

    def _get(self, config, reponame):
        try:
            val = config.get_repo(reponame, self.name)
        except GitoliteConfigException:
            log.exception("Error to get property '%s' on repo '%s'" % (self.name, reponame))
            val = None
        return val

    def trigger(self, config, repobase, name, reponame):
        # repobas -- repositories dir
        # name    -- repositories relative path with '.git' stripped
        # reponame -- name of the repo which @name belongs to
        val = self._get(config, reponame)
        if val != None:
            self.action(repobase, name, reponame, val)
    
class RepositoryDir(object):
    log = logging.getLogger('gitosis.RepositoryDir')

    def __init__(self, config, props):
        self.repositories = getRepositoryDir(config)
        self.config = config
        self.props = props

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

        repo = None
        try:
            repo = config.lookup_repo(name)
        except GitoliteConfigException:
            self.log.exception("When visit repo '%s'" % repo)
            return

        if not repo:
            self.log.warning("No repo contains '%s'" % name)
            return

        for p in props:
            p.trigger(config, repositories, name, repo)

def parse_bool(val):
    if val in ('Yes',   'yes',  'YES',
               'True',  'true', 'TRUE',
               'On',    'on',   'ON',
               '1'):
        return True

    return False

def decode_id(encoded_id):
    prefix = 'git'
    _id = ''

    if encoded_id.startswith(prefix):
        _id = encoded_id[len(prefix):]
        _id = _id.replace('.', '=')
        _id = urlsafe_b64decode(_id)

        if '\n' in _id:
            _id = ''

    return _id
