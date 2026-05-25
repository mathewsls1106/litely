"""Tunnel manager for AWS SSM port forwarding."""
import os
import subprocess
import signal
from dataclasses import dataclass
from typing import Dict, List

import boto3


@dataclass
class TunnelInfo:
    name: str
    tunnel_type: str
    remote_host: str
    remote_port: int
    local_port: int
    process: subprocess.Popen


class TunnelManager:
    def __init__(self):
        self.tunnels: Dict[str, TunnelInfo] = {}
        self.instance_id: str | None = None

    def _session(self):
        profile = os.getenv("AWS_PROFILE")
        region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        if profile:
            return boto3.Session(profile_name=profile, region_name=region)
        return boto3.Session(region_name=region)

    def find_instance(self, tag_name: str) -> str | None:
        session = self._session()
        ec2 = session.client("ec2")
        try:
            resp = ec2.describe_instances(
                Filters=[
                    {"Name": "tag:Name", "Values": [tag_name]},
                    {"Name": "instance-state-name", "Values": ["running"]},
                ]
            )
            self.instance_id = resp["Reservations"][0]["Instances"][0]["InstanceId"]
        except (IndexError, KeyError, Exception):
            self.instance_id = None
        return self.instance_id

    def cleanup_sessions(self, arn: str | None = None) -> None:
        session = self._session()
        if arn is None:
            try:
                sts = session.client("sts")
                arn = sts.get_caller_identity()["Arn"]
            except Exception:
                arn = ""
        if arn:
            ssm = session.client("ssm")
            try:
                resp = ssm.describe_sessions(
                    State="Active",
                    Filters=[{"Key": "Owner", "Value": arn}],
                )
                for s in resp.get("Sessions", []):
                    ssm.terminate_session(SessionId=s["SessionId"])
            except Exception:
                pass
        subprocess.run(["pkill", "-f", "aws ssm start-session"], capture_output=True)
        subprocess.run(["pkill", "-f", "session-manager-plugin"], capture_output=True)

    def _build_cmd(self, tunnel_type: str, remote_host: str, remote_port: int, local_port: int) -> List[str]:
        profile = os.getenv("AWS_PROFILE")
        target = self.instance_id
        if tunnel_type == "port":
            cmd = [
                "aws", "ssm", "start-session", "--target", target,
                "--document-name", "AWS-StartPortForwardingSession",
                "--parameters", f"portNumber={remote_port},localPortNumber={local_port}",
            ]
        else:
            cmd = [
                "aws", "ssm", "start-session", "--target", target,
                "--document-name", "AWS-StartPortForwardingSessionToRemoteHost",
                "--parameters", f"host={remote_host},portNumber={remote_port},localPortNumber={local_port}",
            ]
        if profile:
            cmd += ["--profile", profile]
        return cmd

    def start_tunnel(self, name: str, tunnel_type: str, remote_host: str, remote_port: int, local_port: int) -> None:
        if name in self.tunnels:
            raise RuntimeError(f"Tunnel {name} already running")
        if not self.instance_id:
            raise RuntimeError("No instance ID found")
        cmd = self._build_cmd(tunnel_type, remote_host, remote_port, local_port)
        proc = subprocess.Popen(
            cmd, preexec_fn=os.setsid,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.tunnels[name] = TunnelInfo(name, tunnel_type, remote_host, remote_port, local_port, proc)

    def stop_tunnel(self, name: str) -> None:
        info = self.tunnels.get(name)
        if not info:
            return
        try:
            os.killpg(os.getpgid(info.process.pid), signal.SIGTERM)
            info.process.wait(timeout=5)
        except Exception:
            try:
                info.process.kill()
                info.process.wait()
            except Exception:
                pass
        self.tunnels.pop(name, None)

    def stop_all(self) -> None:
        for name in list(self.tunnels.keys()):
            self.stop_tunnel(name)

    def list_active(self) -> List[TunnelInfo]:
        return list(self.tunnels.values())

    def check_active_tunnels(self) -> Dict[str, bool]:
        """Check which tunnels are still running. Returns dict of name -> is_alive."""
        result = {}
        for name, info in list(self.tunnels.items()):
            if info.process.poll() is None:
                result[name] = True
            else:
                # Process has exited, remove from tunnels
                self.tunnels.pop(name, None)
                result[name] = False
        return result

    def get_dead_tunnels(self) -> List[TunnelInfo]:
        """Return list of tunnels that have died and should be restarted."""
        dead = []
        for name, info in list(self.tunnels.items()):
            if info.process.poll() is not None:
                dead.append(info)
                self.tunnels.pop(name, None)
        return dead
