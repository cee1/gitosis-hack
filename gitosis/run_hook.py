"""
Perform gitosis actions for a git hook.
"""

import errno
import logging
import os
import sys
import shutil

from gitosis import repository
from gitosis import ssh
from gitosis import gitweb
from gitosis import gitdaemon
from gitosis import app
from gitosis import util

log = logging.getLogger('gitosis.run_hook')

def post_update(cfg, git_dir):
    export = os.path.join(git_dir, 'gitosis-export')
    try:
        shutil.rmtree(export)
    except OSError, e:
        if e.errno == errno.ENOENT:
            pass
        else:
            raise
    repository.export(git_dir=git_dir, path=export)
    os.rename(
        os.path.join(export, 'gitosis.conf'),
        os.path.join(export, '..', 'gitosis.conf'),
        )
    # re-read config to get up-to-date settings
    cfg.load(file(os.path.join(export, '..', 'gitosis.conf'), 'r'))

    props = (gitdaemon.DaemonProp(),
      gitweb.GitwebProp(), gitweb.DescriptionProp(), gitweb.OwnerProp())

    ext_props = cfg.get_gitosis('extProps') or ()
    if ext_props:
        try:
            ext_props_expanded = os.path.join(
              os.path.expanduser('~'), ext_props)
            dir_ = os.path.dirname(ext_props_expanded)
            file_ = os.path.basename(ext_props_expanded)
            mod_, ext_ = os.path.splitext(file_)
            assert mod_, "'%s': empty module name" % file_
            assert ext_ == '.py', "the extname of '%s' is not '.py'" % file_

            sys.path.append(dir_)
            mod_ = __import__(mod_)
            ext_props_ = mod_.get_props()
        except (AssertionError, ImportError) as e:
            log.warning("Invalid extProps value '%s': %s" % \
              (ext_props, str(e)))
            ext_props = ()
        except:
            log.warning("Bad module '%s': %s" % \
              (ext_props, str(sys.exc_info()[1])))
            ext_props = ()
        else:
            ext_props = ext_props_

    util.RepositoryDir(cfg, props + ext_props).travel()
    generated = util.getGeneratedFilesDir(config=cfg)
    gitweb.ProjectList(
                      os.path.join(generated, 'projects.list')
                      ).refresh()

    authorized_keys = util.getSSHAuthorizedKeysPath(config=cfg)
    ssh.writeAuthorizedKeys(
        path=authorized_keys,
        keydir=os.path.join(export, 'keydir'),
        )

class Main(app.App):
    def create_parser(self):
        parser = super(Main, self).create_parser()
        parser.set_usage('%prog [OPTS] HOOK')
        parser.set_description(
            'Perform gitosis actions for a git hook')
        return parser

    def handle_args(self, parser, cfg, options, args):
        try:
            (hook,) = args
        except ValueError:
            parser.error('Missing argument HOOK.')

        os.umask(0022)

        git_dir = os.environ.get('GIT_DIR')
        if git_dir is None:
            log.error('Must have GIT_DIR set in enviroment')
            sys.exit(1)

        if hook == 'post-update':
            log.info('Running hook %s', hook)
            post_update(cfg, git_dir)
            log.info('Done.')
        else:
            log.warning('Ignoring unknown hook: %r', hook)
