Release Notes
=============

These are not all encompassing, but we will try and capture noteable differences here.

----
# 1.0
### v1.0 release includes some significant changes, attempting to capture major differences here
* migrated core API interactions to use  the official [Python MESH Client](https://github.com/NHSDigital/mesh-client), which sends [application/vnd.mesh.v2+json](https://digital.nhs.uk/developer/api-catalogue/message-exchange-for-social-care-and-health-api)
* as a result of the move to v2 MESH api features there will be some slight differences:
  * message status headers value will be lowercase status: `accepted`, `acknowledged`, rather than capitalised `Accepted`, `Acknowledged` and so forth.
  * mex header names are all lower case
