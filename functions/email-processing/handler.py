from __future__ import print_function
import os
import sys

here = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(here, 'vendored', 'lib', 'python2.7', 'site-packages'))
sys.path.append(os.path.join(here, 'vendored', 'lib64', 'python2.7', 'site-packages'))

import email
import json
import logging

import boto3

from s3 import decrypt_object
from ses import is_valid_receipt

log = logging.getLogger('email-processing')
log.setLevel(logging.DEBUG)


def construct_outgoing_message(source, content):
    message = """
    Hey {source}!

    You just sent me:

        {content}

    Thanks!
    """.format(source=source, content=content)
    return message


def handler(event, context):
    log.debug('Received event:\n\n{}'.format(json.dumps(event, indent=4)))
    s3 = boto3.client('s3')
    kms = boto3.client('kms', region_name=os.environ['SERVERLESS_REGION'])
    ses = boto3.client('ses', region_name=os.environ['SERVERLESS_REGION'])
    for record in event['Records']:
        log.debug('Processing record:\n\n{}'.format(json.dumps(record, indent=4)))
        receipt = record['ses']['receipt']
        log.debug('Validating receipt:\n\n{}'.format(json.dumps(receipt, indent=4)))

        # Ensure the receipt is valid (passed all checks)
        valid, message = is_valid_receipt(receipt)
        if not valid:
            log.error('Invalid receipt:\n\n{}'.format(message))
            continue

        message_id = record['ses']['mail']['messageId']
        source = record['ses']['mail']['source']
        bucket = os.environ['SES_S3_BUCKET']
        key = os.path.join(os.environ['SES_S3_PREFIX'], message_id)

        # Fetch the decrypted payload from s3
        payload = decrypt_object(s3, kms, bucket, key)

        # Process the message
        message = email.message_from_string(payload)
        content = ''
        for part in message.get_payload():
            if part.get_content_type() == 'text/plain':
                content = part.get_payload().strip()

        # Echo the message we received
        outgoing_message = construct_outgoing_message(source, content)
        log.debug('Sending outgoing message:\n\n{}'.format(outgoing_message))
        response = ses.send_email(
            Source=os.environ['SES_SOURCE'],
            Destination={
                'ToAddresses': [source],
            },
            Message={
                'Subject': {
                    'Data': 'Echo: {}'.format(message.get('subject')),
                    'Charset': 'utf-8',
                },
                'Body': {
                    'Text': {
                        'Data': outgoing_message,
                        'Charset': 'utf-8',
                    },
                },
            },
        )
        log.debug('Sent outgoing message:\n\n{}'.format(json.dumps(response, indent=4)))
