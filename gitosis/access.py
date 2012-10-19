import os, logging

from gitosis import group
from gitosis.gitoliteConfig import GitoliteConfigException

def haveAccess(config, user, mode, path):
    """
    Map request for write access to allowed path.

    Note for read-only access, the caller should check for write
    access too.

    Returns ``None`` for no access, or a tuple of toplevel directory
    containing repositories and a relative path to the physical repository.
    """
    detail = []
    log = logging.getLogger('gitosis.access.haveAccess')

    log.debug(
        'Access check for %(user)r as %(mode)r on %(path)r...'
        % dict(
        user=user,
        mode=mode,
        path=path,
        ))

    basename, ext = os.path.splitext(path)
    if ext == '.git':
        log.debug(
            'Stripping .git suffix from %(path)r, new value %(basename)r'
            % dict(
            path=path,
            basename=basename,
            ))
        path = basename

    repo = None
    try:
        repo = config.lookup_repo(path)
    except GitoliteConfigException:
        log.exception("When lookup which repo contains '%s'" % path)

    if not repo:
        log.warning("No repo contains path '%s'" % path)
        return

    mapping = None
    try:
        users = config.get_repo(repo, mode)
    except GitoliteConfigException:
        log.exception("When get '%s' of '%s':" % (mode, repo))
        return

    if users:
        if user in users:
            mapping = path
        else:
            for groupname in group.getMembership(config=config, user=user):
                if groupname in users:
                    mapping = path
                    detail.append("as group '%s'" % groupname)
                    break
            
    if mapping is not None:
        if detail:
            detail = '(%s)' % ', '.join(detail)
        else:
            detail = ''

        log.debug(
            'Access ok for %(user)r as %(mode)r on %(path)r(%(detail)s)'
            % dict(
            user=user,
            mode=mode,
            path=path,
            detail=detail
            ))

        prefix = config.get_gitosis('repositories')
        if prefix == None:
            prefix = 'repositories'

        log.debug(
            'Using prefix %(prefix)r for %(path)r'
            % dict(
            prefix=prefix,
            path=mapping,
            ))
        return (prefix, mapping)
