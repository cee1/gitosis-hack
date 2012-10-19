import logging
from gitosis.gitoliteConfig import GitoliteConfigException

def _getMembership(config, user, seen):
    log = logging.getLogger('gitosis.group.getMembership')

    for group in config.groups():
        try:
            members = config.get_group_members(group)
        except GitoliteConfigException:
            log.exception("When list members of '%s':" % group)
            members = None

        if members:
            # @all is the only group where membership needs to be
            # bootstrapped like this, anything else gets started from the
            # username itself
            if (user in members
                or '@all' in members):
                log.debug('found %(user)r in %(group)r' % dict(
                    user=user,
                    group=group,
                    ))
                seen.add(group)
                yield group

                for member_of in _getMembership(
                    config, group, seen,
                    ):
                    yield member_of


def getMembership(config, user):
    """
    Generate groups ``user`` is member of, according to ``config``

    :type config: RawConfigParser
    :type user: str
    :param _seen: internal use only
    """

    seen = set()
    for member_of in _getMembership(config, user, seen):
        yield member_of

    # everyone is always a member of group "all"
    yield '@all'

