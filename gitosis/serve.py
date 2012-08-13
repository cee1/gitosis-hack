"""
Enforce git-shell to only serve allowed by access control policy.
directory. The client should refer to them without any extra directory
prefix. Repository names are forced to match ALLOW_RE.
"""

import logging

import sys, os, re

from gitosis import access
from gitosis import repository
from gitosis import gitweb
from gitosis import gitdaemon
from gitosis import app
from gitosis import util

log = logging.getLogger('gitosis.serve')

ALLOW_RE = re.compile("^'/*(?P<path>[a-zA-Z0-9][a-zA-Z0-9@._-]*(/[a-zA-Z0-9][a-zA-Z0-9@._-]*)*)'$")

COMMANDS_READONLY = [
    'git-upload-pack',
    'git upload-pack',
    ]

COMMANDS_WRITE = [
    'git-receive-pack',
    'git receive-pack',
    ]

class ServingError(Exception):
    """Serving error"""

    def __str__(self):
        return '%s' % self.__doc__

class CommandMayNotContainNewlineError(ServingError):
    """Command may not contain newline"""

class UnknownCommandError(ServingError):
    """Unknown command denied"""

class UnsafeArgumentsError(ServingError):
    """Arguments to command look dangerous"""

class BadEncodedID(ServingError):
    """Bad encoded user id"""

class AccessDenied(ServingError):
    """Access denied to repository"""

class BadRepositoryPath(ServingError):
    """Intermediate repository path contains component ends with '.git'"""

class WriteAccessDenied(AccessDenied):
    """Repository write access denied"""

class ReadAccessDenied(AccessDenied):
    """Repository read access denied"""

def serve(
    cfg,
    user,
    command,
    ):
    if '\n' in command:
        raise CommandMayNotContainNewlineError()

    try:
        verb, args = command.split(None, 1)
    except ValueError:
        # all known "git-foo" commands take one argument; improve
        # if/when needed
        raise UnknownCommandError()

    if verb == 'git':
        try:
            subverb, args = args.split(None, 1)
        except ValueError:
            # all known "git foo" commands take one argument; improve
            # if/when needed
            raise UnknownCommandError()
        verb = '%s %s' % (verb, subverb)

    if (verb not in COMMANDS_WRITE
        and verb not in COMMANDS_READONLY):
        raise UnknownCommandError()

    match = ALLOW_RE.match(args)
    if match is None:
        raise UnsafeArgumentsError()

    path = match.group('path')

    decode_id = cfg.get_gitosis('decodeID')
    if decode_id and util.parse_bool(decode_id):
        encoded_user = user
        user = util.decode_id(encoded_user)

        log.debug("decodeID = yes, decode '%s' as '%s'" % (encoded_user, user))

        if not user:
            raise BadEncodedID()

    newpath = access.haveAccess(
            config=cfg,
            user=user,
            mode='RW+',
            path=path)

    if newpath == None:
        if verb in COMMANDS_WRITE:
            raise WriteAccessDenied()
        else:
            newpath = access.haveAccess(
                config=cfg,
                user=user,
                mode='R',
                path=path)

            if newpath == None:
                raise ReadAccessDenied()
    
    (repobase, reponame) = newpath
    assert not reponame.endswith('.git'), \
           'git extension should have been stripped: %r' % reponame
    repopath = reponame + '.git'
    fullpath = os.path.join(repobase, repopath)
    if not os.path.exists(fullpath):
        # it doesn't exist on the filesystem, but the configuration
        # refers to it, we're serving a write request, and the user is
        # authorized to do that: create the repository on the fly

        # create leading directories
        p = repobase
        components = repopath.split(os.sep)[:-1]
        for c in components: # Check
            if c.endswith('.git'):
                raise BadRepositoryPath()
        for c in components:
            p = os.path.join(p, c)
            util.mkdir(p, 0750)

        repository.init(path=fullpath)
        util.RepositoryDir(cfg,
                  (
                  gitdaemon.DaemonProp(),
                  gitweb.GitwebProp(),
                  gitweb.DescriptionProp(),
                  gitweb.OwnerProp()
                  )).visit_one(reponame)
        generated = util.getGeneratedFilesDir(config=cfg)
        gitweb.ProjectList(
                          os.path.join(generated, 'projects.list')
                          ).update()

    # put the verb back together with the new path
    newcmd = "%(verb)s '%(path)s'" % dict(
        verb=verb,
        path=fullpath,
        )
    return newcmd

class Main(app.App):
    def create_parser(self):
        parser = super(Main, self).create_parser()
        parser.set_usage('%prog [OPTS] USER')
        parser.set_description(
            'Allow restricted git operations under DIR')
        return parser

    def handle_args(self, parser, cfg, options, args):
        try:
            (user,) = args
        except ValueError:
            parser.error('Missing argument USER.')

        main_log = logging.getLogger('gitosis.serve.main')
        os.umask(0022)

        cmd = os.environ.get('SSH_ORIGINAL_COMMAND', None)
        if cmd is None:
            main_log.error('Need SSH_ORIGINAL_COMMAND in environment.')
            sys.exit(1)

        main_log.debug('Got command %(cmd)r' % dict(
            cmd=cmd,
            ))

        os.chdir(os.path.expanduser('~'))

        try:
            newcmd = serve(
                cfg=cfg,
                user=user,
                command=cmd,
                )
        except ServingError, e:
            main_log.error('%s', e)
            sys.exit(1)

        main_log.debug('Serving %s', newcmd)
        os.execvp('git', ['git', 'shell', '-c', newcmd])
        main_log.error('Cannot execute git-shell.')
        sys.exit(1)
