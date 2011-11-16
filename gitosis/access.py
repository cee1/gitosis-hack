import os, logging, re
from ConfigParser import NoSectionError, NoOptionError

from gitosis import group

def haveAccess(config, user, mode, path):
    """
    Map request for write access to allowed path.

    Note for read-only access, the caller should check for write
    access too.

    Returns ``None`` for no access, or a tuple of toplevel directory
    containing repositories and a relative path to the physical repository.
    """
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

    for groupname in group.getMembership(config=config, user=user):
        section = 'group %s' % groupname

        mapping = None
        reason = ''

        try:
            repos = config.get(section, mode)
        except (NoSectionError, NoOptionError):
            continue
        else:
            repos = repos.split()

        for r in repos:
            if r == path: # exactly match: match [repo %s] or implict [repo %s]
                mapping = path
                break

            try:
                p = config.get('repo %s' % r, 'path')
            except (NoSectionError, NoOptionError):
                pass
            else:
                if re.match(p, path):
                    mapping = path
                    reason = ' ([repo %s].path=%r)' % (r, p)
                    break

        if mapping is not None:
            log.debug(
                'Access ok for %(user)r as %(mode)r on %(path)r%(reason)s'
                % dict(
                user=user,
                mode=mode,
                path=path,
                reason=reason,
                ))

            prefix = None
            try:
                prefix = config.get('gitosis', 'repositories')
            except (NoSectionError, NoOptionError):
                prefix = 'repositories'

            log.debug(
                'Using prefix %(prefix)r for %(path)r'
                % dict(
                prefix=prefix,
                path=mapping,
                ))
            return (prefix, mapping)
