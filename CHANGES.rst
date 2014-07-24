Changelog
=========

1.1 (unreleased)
----------------

- Add MLS logo and use higher resolution images where available.

- Always load cdn.mozilla.net resources over https.

- Updated deployment docs to more clearly mention the Redis dependency
  and clean up Heka / logging related docs.

- Split out circus and its dependencies into a separate requirements file.

- Remove non-local debug logging from map tiles generation script.

- Test all additional fields in geosubmit API and correctly retain new
  `signalToNoiseRatio` field for WiFi observations.

- Improve geosubmit API docs and make them independent of the submit docs.

- Update and tweak metrics docs.

- Adjust Fennec link to point to Fennec Nightly install instructions.
  https://bugzilla.mozilla.org/show_bug.cgi?id=1039787

20140715114000
**************

- Adjust beat schedule to update more rows during each location update task.

- Let the backup tasks retain three full days of measures in the DB.

- Remove the database connectivity test from the heartbeat view.


1.0 (2014-07-14)
----------------

- Initial production release.

0.1 (2013-11-22)
----------------

- Initial prototype.
