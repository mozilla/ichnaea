#!/usr/bin/env python
"""
Send Sentry errors to test configuration and connectivity.
"""

import datetime

import click

from ichnaea.conf import settings
from ichnaea.data.tasks import sentry_test
from ichnaea.log import configure_logging, configure_raven
from ichnaea.taskapp.app import celery_app
from ichnaea.taskapp.config import init_worker


@click.group()
def sentry_test_group():
    pass


@sentry_test_group.command("clitest")
@click.pass_context
def cmd_clitest(ctx):
    """Run Sentry test through cli."""
    sentry_dsn = settings("sentry_dsn")
    if not sentry_dsn:
        click.echo(
            click.style(
                "SENTRY_DSN is not configured so this will use DebugRavenClient.",
                fg="green",
            )
        )

    msg = "Testing Sentry configuration via cli (%s)" % str(datetime.datetime.now())
    click.echo(click.style("Using message: %s" % msg, fg="green"))
    click.echo(click.style("Building Raven client...", fg="green"))
    client = configure_raven(transport="sync")
    click.echo(click.style("Sending message...", fg="green"))
    client.captureMessage(msg)


@sentry_test_group.command("celerytest")
@click.pass_context
def cmd_celerytest(ctx):
    """Run Sentry test through celery.

    This creates a celery task which will send an event to Sentry
    when it's executed.

    """
    configure_logging()
    init_worker(celery_app)

    msg = "Testing Sentry configuration via celery (%s)" % str(datetime.datetime.now())
    click.echo(click.style("Using message: %s" % msg, fg="green"))
    click.echo(click.style("Creating celery task...", fg="green"))
    sentry_test.delay(msg=msg)


if __name__ == "__main__":
    sentry_test_group()
