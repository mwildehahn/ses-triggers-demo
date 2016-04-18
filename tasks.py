import json
import logging
import os
import sys

import boto3
from invoke import task
import yaml

logging.basicConfig(
    format='[%(asctime)s] %(name)s %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    stream=sys.stdout,
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DEFAULT_SETTINGS_FILE = 'defaults.yaml'
OVERRIDE_SETTINGS_FILE = 'overrides.yaml'
MX_RECORD_PATH = '_meta/resources/demo-resources-mx-record.json'
SES_RECORD_PATH = '_meta/resources/demo-resources-ses-record.json'

REQUIRED_KEYS = [
    ('hosted_zone_id', 'Maps to a hosted zone within route53'),
    ('subdomain', 'The subdomain you want to use as the email endpoint'),
    ('ses_inbound_endpoint', 'The SES inbound endpoint for the region you want to deploy to'),
    ('rule_name', 'SES Receipt Rule name'),
    ('username', 'Username you want to enable as a recipient'),
    ('s3_bucket', 'The name of the S3 bucket you want to use'),
    ('s3_prefix', 'The prefix you wanto to use for incoming messages within S3'),
    ('aws_region', 'The AWS region you want to deploy within'),
    ('lambda_arn', 'The ARN for the lambda function you want to hook up to the SES rule'),
]


def _format_fqn_for_ses(fqn):
    # remove trailing ".", SES doesn't treat this as a valid domain
    ses_fqn = fqn
    if ses_fqn.endswith('.'):
        ses_fqn = ses_fqn[:-1]
    return ses_fqn


def _verify_response(response, status_code=200):
    return response['ResponseMetadata']['HTTPStatusCode'] == status_code


def _get_account_id():
    iam = boto3.client('iam')
    return iam.get_user()['User']['Arn'].split(':')[4]


def _get_settings():
    overrides = {}
    with open(DEFAULT_SETTINGS_FILE, 'r') as default_file:
        settings = yaml.load(default_file)

    if os.path.exists(OVERRIDE_SETTINGS_FILE):
        with open(OVERRIDE_SETTINGS_FILE, 'r') as overrides_file:
            overrides = yaml.load(overrides_file)

    settings.update(overrides)
    error = False
    for key, message in REQUIRED_KEYS:
        if key not in settings:
            error = True
            logger.error(
                'Must provide key: `%s` (%s)',
                key,
                message,
            )
    if error:
        sys.exit(1)
    return settings


def _get_fqn(route53_client, subdomain, hosted_zone_id):
    hosted_zone = route53_client.get_hosted_zone(Id=hosted_zone_id)
    return '%s.%s' % (subdomain, hosted_zone['HostedZone']['Name'])


def _change_resource_record_sets(
        route53,
        record_set,
        comment,
        hosted_zone_id,
        record_path=None,
        delete=False,
    ):
    if delete:
        action = 'DELETE'
    else:
        action = 'CREATE'

    action = {
        'Action': action,
        'ResourceRecordSet': record_set,
    }
    batch = {
        'Comment': comment,
        'Changes': [action],
    }
    logger.info('%s:\n%s', comment, {'hosted_zone_id': hosted_zone_id, 'batch': batch})
    response = route53.change_resource_record_sets(HostedZoneId=hosted_zone_id, ChangeBatch=batch)
    if not delete and record_path and _verify_response(response):
        with open(record_path, 'w') as write_file:
            json.dump(record_set, write_file)
    elif delete and record_path:
        os.remove(record_path)
    return response


def _get_mx_record_set(route53, subdomain, hosted_zone_id, ses_inbound_endpoint, **kwargs):
    fqn = _get_fqn(route53, subdomain, hosted_zone_id)
    record_set = {
        'Name': fqn,
        'Type': 'MX',
        'TTL': 1800,
        'ResourceRecords': [{'Value': '10 %s' % (ses_inbound_endpoint,)}],
    }
    return record_set


def _create_mx_record_for_subdomain(subdomain, hosted_zone_id, ses_inbound_endpoint, **kwargs):
    route53 = boto3.client('route53')
    record_set = _get_mx_record_set(route53, subdomain, hosted_zone_id, ses_inbound_endpoint)

    comment = 'Creating "MX" record for subdomain: "%s"' % (subdomain,)
    return _change_resource_record_sets(
        route53,
        record_set,
        comment,
        hosted_zone_id,
        record_path=MX_RECORD_PATH,
    )


def _delete_mx_record_for_subdomain(subdomain, hosted_zone_id, **kwargs):
    route53 = boto3.client('route53')
    with open(MX_RECORD_PATH, 'r') as read_file:
        record_set = json.load(read_file)

    comment = 'Deleting "MX" record for subdomain: "%s"' % (subdomain,)
    return _change_resource_record_sets(
        route53,
        record_set,
        comment,
        hosted_zone_id,
        delete=True,
        record_path=MX_RECORD_PATH,
    )


def _get_ses_verification_record_set(route53, subdomain, hosted_zone_id, token):
    fqn = _get_fqn(route53, subdomain, hosted_zone_id)
    record_set = {
        'Name': '_amazonses.%s' % (fqn,),
        'Type': 'TXT',
        'TTL': 1800,
        'ResourceRecords': [{'Value': '"%s"' % (token,)}],
    }
    return record_set


def _create_ses_verification_record_for_subdomain(
        subdomain,
        hosted_zone_id,
        ses_inbound_endpoint,
        aws_region,
        **kwargs
    ):
    route53 = boto3.client('route53')
    ses = boto3.client('ses', region_name=aws_region)
    fqn = _get_fqn(route53, subdomain, hosted_zone_id)
    ses_fqn = _format_fqn_for_ses(fqn)

    response = ses.verify_domain_identity(Domain=ses_fqn)
    verification_token = response['VerificationToken']
    record_set = _get_ses_verification_record_set(
        route53,
        subdomain,
        hosted_zone_id,
        verification_token,
    )

    comment = 'Creating SES "TXT" verification record for subdomain: "%s"' % (subdomain,)
    return _change_resource_record_sets(
        route53,
        record_set,
        comment,
        hosted_zone_id,
        record_path=SES_RECORD_PATH,
    )


def _delete_ses_verification_record_for_subdomain(subdomain, hosted_zone_id, **kwargs):
    route53 = boto3.client('route53')
    with open(SES_RECORD_PATH, 'r') as read_file:
        record_set = json.load(read_file)

    comment = 'Deleting SES "TXT" verification record for subdomain: "%s"' % (subdomain,)
    return _change_resource_record_sets(
        route53,
        record_set,
        comment,
        hosted_zone_id,
        delete=True,
        record_path=SES_RECORD_PATH,
    )


def _create_rules(
        rule_set_name,
        rule_name,
        subdomain,
        hosted_zone_id,
        s3_bucket,
        lambda_arn,
        username,
        s3_prefix,
        aws_region,
        **kwargs
    ):
    route53 = boto3.client('route53')
    ses = boto3.client('ses', region_name=aws_region)
    fqn = _get_fqn(route53, subdomain, hosted_zone_id)
    ses_fqn = _format_fqn_for_ses(fqn)
    aws_account_id = _get_account_id()
    logger.info('creating receipt rule set: %s...', rule_set_name)
    ses.create_receipt_rule_set(RuleSetName=rule_set_name)
    logger.info('...created receipt rule set')
    logger.info('creating receipt rule: %s (%s)...', rule_name, lambda_arn)
    ses.create_receipt_rule(
        RuleSetName=rule_set_name,
        Rule={
            'Name': rule_name,
            'Enabled': True,
            'ScanEnabled': True,
            'TlsPolicy': 'Require',
            'Recipients': [
                '%s@%s' % (username, ses_fqn),
            ],
            'Actions': [
                {'S3Action': {
                    'BucketName': s3_bucket,
                    'ObjectKeyPrefix': s3_prefix,
                    'KmsKeyArn': 'arn:aws:kms:%s:%s:alias/aws/ses' % (
                        aws_region,
                        aws_account_id,
                    ),
                }},
                {'LambdaAction': {
                    'FunctionArn': lambda_arn,
                }},
            ],
        }
    )
    ses.set_active_receipt_rule_set(RuleSetName=rule_set_name)
    logger.info('...created receipt rule')


def _delete_rules(rule_set_name, aws_region, **kwargs):
    ses = boto3.client('ses', region_name=aws_region)
    ses.set_active_receipt_rule_set()
    ses.delete_receipt_rule_set(RuleSetName=rule_set_name)


@task
def create():
    """Creates the required SES records.

    This works specifically if you're launching within an existing hosted zone.
    It assumes you have defined the following values in either a
    `defaults.yaml` or `overrides.yaml` file:

        hosted_zone_id
        subdomain
        ses_inbound_endpoint

    """
    settings = _get_settings()
    logger.info('Creating SES records with the following config:\n%s', str(settings))
    _create_ses_verification_record_for_subdomain(**settings)
    _create_mx_record_for_subdomain(**settings)
    _create_rules(**settings)
    logger.info('...successfully configured SES records and rules')


@task
def teardown():
    """Tears down SES DNS and Receipt Rules we've created.

    - SES Verification Record
    - SES MX Record
    - Receipt Rule Set
    - Receipt Rules

    """
    settings = _get_settings()
    logger.info('Tearing down SES records with the following config:\n%s', settings)
    _delete_mx_record_for_subdomain(**settings)
    _delete_ses_verification_record_for_subdomain(**settings)
    _delete_rules(**settings)
    logger.info('...successfully tore down records')
