"""Credential helper for AWS SSO."""
import os
import subprocess
import datetime
from typing import Tuple
import boto3

def _run_aws_sso_login(profile: str) -> None:
    subprocess.run(["aws", "sso", "login", "--profile", profile], check=False)

def _get_session(profile: str):
    return boto3.Session(profile_name=profile) if profile else boto3.Session()

def get_identity() -> Tuple[str, datetime.datetime]:
    """Return (ARN, expiration) for current AWS credentials.
    If expires within 2 minutes, trigger `aws sso login`.
    """
    profile = os.getenv("AWS_PROFILE")
    session = _get_session(profile)
    cred = session.get_credentials()
    if cred is None:
        raise RuntimeError("Unable to obtain AWS credentials")
    expiry = cred._expiry_time  # type: ignore
    if expiry is None:
        # No expiry (e.g., static credentials), use a far-future date
        expiry = datetime.datetime(2099, 12, 31, tzinfo=datetime.timezone.utc)
    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    if expiry - now < datetime.timedelta(minutes=2):
        _run_aws_sso_login(profile or "default")
        session = _get_session(profile)
        cred = session.get_credentials()
        expiry = cred._expiry_time  # type: ignore
        if expiry is None:
            expiry = datetime.datetime(2099, 12, 31, tzinfo=datetime.timezone.utc)
    sts = session.client("sts")
    arn = sts.get_caller_identity()["Arn"]
    return arn, expiry
