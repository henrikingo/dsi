"""
Functionality to list build failures and their linked change points.
"""
from __future__ import print_function

from datetime import datetime
import sys

import structlog

import jinja2

from signal_processing.commands.helpers import stringify_json

LOG = structlog.getLogger(__name__)
JIRA_LINK_PREFIX = 'https://jira.mongodb.org/browse/'


def format_change_point(change_point):
    """
    Jinja2 helper to summarize a change_point.

    :param change_point: change_point to summarize.
    :return: change_point summary.
    """
    return '{}/{}/{}/{}/{}'.format(change_point['project'], change_point['variant'],
                                   change_point['task'], change_point['test'],
                                   change_point['thread_level'])


def format_short_list(short_list):
    """
    Jinja2 helper format a short list.

    :param short_list: list to format.
    :return: formatted list.
    """
    return ', '.join(short_list)


def format_jira_link(jira_ticket):
    """
    Jinja2 helper format a jira link.

    :param jira_ticket: jira ticket to format.
    :return: jira link.
    """
    return '[{jira_ticket}]({jira_prefix}{jira_ticket})'.format(
        jira_ticket=jira_ticket, jira_prefix=JIRA_LINK_PREFIX)


HUMAN_READABLE_TEMPLATE_STR = '''
[ {{ now() }} ] Running: `{{ command_line }}`

{% for bf in build_failures %}
- ID: {{ format_jira_link(bf._id) }}  
  Summary: {{ '{:80.80}'.format(bf.get('summary', '')) }}  
  Match Revision: {{ bf.revision }}  
  First Failing Revision: {{ format_short_list(bf.first_failing_revision) }}  
  Fix Revision: {{ format_short_list(bf.fix_revision) }}  
  Project(s): {{ format_short_list(bf.project) }}  
  Variant(s): {{ format_short_list(bf.buildvariants) }}
  Task(s): {{ format_short_list(bf.tasks) }}
  Change points: 
  {% for cp in bf.linked_change_points -%}
  - {{ format_change_point(cp) }}  
    All Suspect Revisions: 
    {% for revision in cp.all_suspect_revisions -%}
    - {{ revision }}
    {% endfor %}  
  {% endfor %}  
  
{% endfor %}
'''

ENVIRONMENT = jinja2.Environment()
ENVIRONMENT.globals.update({
    'command_line': " ".join([value if value else "''" for value in sys.argv]),
    'now': datetime.utcnow,
    'format_change_point': format_change_point,
    'format_jira_link': format_jira_link,
    'format_short_list': format_short_list,
})
HUMAN_READABLE_TEMPLATE = ENVIRONMENT.from_string(HUMAN_READABLE_TEMPLATE_STR)


def render_human_readable_bfs(build_failures):
    """
    Render the list of build failures in a human readable format.

    :param build_failures: build failures to render.
    :return: a human readable (markdown) version of the build failures.
    """
    return ''.join(HUMAN_READABLE_TEMPLATE.stream(build_failures=build_failures))


def list_build_failures(query, human_readable, command_config):
    """
    Print a list of build failures with linked change points.

    :param dict query: Find linked build failures matching this query.
    :param bool human_readable: Print in a more human-friendly format.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('Print build failures')
    collection = command_config.database.linked_build_failures

    # TODO: Get rid of the following four lines once field names are consistent across collections
    # (PERF-1590).
    if 'variant' in query:
        query['buildvariants'] = query.pop('variant')
    if 'task' in query:
        query['tasks'] = query.pop('task')

    if 'suspect_revision' in query:
        suspect_revision = query.pop('suspect_revision')
        if suspect_revision:
            query['revision'] = suspect_revision

    if human_readable:
        print(render_human_readable_bfs(collection.find(query)))
    else:
        for build_failure in collection.find(query):
            print(stringify_json(build_failure, command_config.compact))
