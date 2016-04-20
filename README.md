# Demo of SES Receipt Rules

NOTE: below instructions are a WIP!!!

Example of how you can use SES Receipt Rules to build email integrations.

To run this example, it requires an AWS account linked to an existing hosted zone that you own.

You should first fill in the required parameters within the
`overrides.yaml.sample` file and then rename the file to `overrides.yaml`.

Once you've done that, you can invoke the `create` task:

```
$ docker run -v .:/app mhahn/ses-triggers-demo create
```

This will create with the following default values as defined in `defaults.yaml`:
- An S3 bucket (`s3_bucket`)
- An MX record for `subdomain` within the specified hosted zone
- A TXT verification record for the subdomain within the specified hosted zone
- An SES Receipt Rule Set (`ruleset_name`)
- An SES Receipt Rule for `username`@`subdomain`.`hosted_zone`
