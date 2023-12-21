Release Notes
=============

These are not all encompassing, but we will try and capture noteable differences here.

----
# 2.0
### v2.0 Major release
* Send parameters from [S3 object metadata](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingMetadata.html)
  * MESH `mex-*` headers will be honoured and passed the [MESH Client](https://github.com/NHSDigital/mesh-client), where appropriate  
  * metadata will be inspected first for a `mex-from` (sender mailbox id), metadata parameter, if present this and other metadata will be used, if `mex-from` is not found, we will fall-back to using the outbound mappings as the source for `mex-from`, `mex-to` and `mex-workflowid`
  * S3 object metadata supports a limited character set, and size; Metadata values should be encoded with the equivalent of [urllib.parse.quote_plus](https://docs.python.org/3/library/urllib.parse.html), e.g.  `s3_client.put_object(..., Metadata={"mex-subject": quote_plus(subject),..)` ... before sending to MESH the inverse `unquote_plus` will be applied.
  * `mex-` metadata keys are case-insensitive, keys will be converted to lower case before comparison or sending to MESH.
  * using s3 object metadata allows the configuration of many more mesh parameters, including but not limited to:
    * `mex-from` sender MESH mailbox id (your mailbox)
    * `mex-to` recipient MESH mailbox id (recipient mailbox)
    * `mex-workflowid` MESH workflow id
    * `mex-subject` (optional) 'free text' subject area,  
    * `mex-localid` (optional) sender supplied unique identifier
    * `mex-filename` (optional) passthrough file name passed to recipient, if not set MESH will set a default file name of `{message_id}.dat`
    * `mex-content-compress` (optional) explicit instruction to compress the content before sending to MESH, this will override exclusions based on `mex-content-compressed` and `content-encoding`
    * `mex-content-compressed` (optional) passthrough indication this file is already compressed, if set the send application will never auto-compress, regardless of the file size and `compress_threshold` configured
    * `mex-content-encrypted` (optional) passthrough indicator to signify that the file has been encrypted (MESH does nothing with this)
  
* Significant work on deprecating SSM configuration being created by the module:
  * existing essential configuration parameters (client certificate, shared key,  mailbox passwords) and such have been migrated to data sources using terraform [move](https://developer.hashicorp.com/terraform/language/modules/develop/refactoring) statements. This will ensure required parameters are available, but without this module managing their creation / destruction.
  * un-used / non-essential SSM parameters have been removed.
* Removal of pre-created `application/x-directory` aws_s3_bucket_object resources, these were a deprecated resource.
  * NOTE: removal of an `application/x-directory` object **does not delete the 'directory' contents**, directory object is just another empty object in your bucket.
* Default behaviour of the module is still to monitor for any key with prefix `outbound` so existing send locations will continue to work but also any sub key will also work ... e.g.  `key=f"outbound/{my_id}.json"` will work just fine, or any other key you like under `outbound/`
* Module supports concurrent sending, send message step function is not limited to sending one file at a time, though concurrently sending the same file twice in parallel is still denied to avoid accidental duplicate writes.
* Major overhaul of the module variables, removed the `var.config` in favour of individual variables, support for more configuration, see [README.md](README.md) or [variables.tf](module/variables.tf) for full details.
* terraform module `account_admin_role` variable removed, management of required permissions should be maintained outside the module using `module.mesh.mesh_kms_key_arn` and `module.mesh.mesh_s3_bucket_name` outputs
* `mex-filename` was previously set from the `os.path.basename(s3_object.key)` this is a dangerous default, as the s3 filename could contain sensitive information, if you wish to set the `mex-filename` for the recipient, use the `mex-filename` in s3 object metadata.


# 1.0
### v1.0 release includes some significant changes, attempting to capture major differences here
* migrated core API interactions to use the official [Python MESH Client](https://github.com/NHSDigital/mesh-client), which sends [application/vnd.mesh.v2+json](https://digital.nhs.uk/developer/api-catalogue/message-exchange-for-social-care-and-health-api)
* as a result of the move to v2 MESH api features there will be some slight differences:
  * message status headers value will be lowercase status: `accepted`, `acknowledged`, rather than capitalised `Accepted`, `Acknowledged` and so forth.
  * `mex-*` header names are all lower case  ( though requests `Response.headers` is a CaseInsensitiveDict so this should not matter )
  * `mex-*` metadata will be stored with in the s3 object metadata for a received object.
