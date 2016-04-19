REQUIRED_VERDICTS = ['dkimVerdict', 'spamVerdict', 'spfVerdict', 'virusVerdict']


def is_valid_receipt(receipt):
    """For the above REQUIRED_VERDICTS ensure they've all passed.

    Args:
        receipt (dict): SES receipt

    Returns:
        (bool, str) tuple of whether or not the receipt is valid and the
        message if it was not

    """
    valid = True
    message = ''
    for verdict in REQUIRED_VERDICTS:
        if receipt[verdict]['status'] != 'PASS':
            valid = False
            message = 'Required verdict: %s failed (%s)' % (
                verdict,
                receipt[verdict]
            )
            break
    return valid, message
