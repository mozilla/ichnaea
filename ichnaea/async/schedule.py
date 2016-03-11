"""
Contains the `Celery Beat schedule
<http://celery.rtfd.org/en/latest/userguide/periodic-tasks.html>`_.
"""


def celerybeat_schedule(app_config):
    """Return the celery beat schedule as a dictionary."""
    from ichnaea.data import tasks

    sections = app_config.sections()

    task_names = [
        'monitor_api_key_limits',
        'monitor_api_users',
        'monitor_queue_size',
        'schedule_export_reports',
        'update_blue',
        'update_cell',
        'update_cellarea',
        'update_cellarea_ocid',
        'update_datamap',
        'update_incoming',
        'update_score',
        'update_statcounter',
        'update_statregion',
        'update_wifi',
    ]

    if 'assets' in sections and app_config.get('assets', 'bucket', None):
        # Only configure tasks if target bucket is configured.
        task_names.extend([
            'cell_export_diff',
            'cell_export_full',
        ])

    if 'import:ocid' in sections:
        # Only configure OCID tasks if OCID section is configured.
        task_names.extend([
            'cell_import_external',
            'monitor_ocid_import',
        ])

    schedule = {}
    for task_name in task_names:
        schedule.update(getattr(tasks, task_name).beat_config())

    return schedule
