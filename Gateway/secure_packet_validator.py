"""Secure packet validation pipeline for SmartSeal+."""

from Gateway.key_manager import get_device_key
from Gateway.message_auth import verify_hmac
from Gateway.replay_protection import ReplayProtector


class SecurePacketValidator:
    """Authenticate sensor packets and reject replayed events."""

    def __init__(self):
        self.replay_protector = ReplayProtector()

    def validate_packet(self, packet):
        """
        Validate an incoming SmartSeal+ sensor packet.

        Returns:
            (True, "accepted") when validation succeeds.
            (False, reason) when validation fails.
        """

        if not isinstance(packet, dict):
            return False, "invalid packet format"

        seal_id = packet.get("seal_id")
        sequence = packet.get("event_sequence")
        received_hmac = packet.get("hmac")

        # Step 1: Validate device identity format.
        if (
            not isinstance(seal_id, int)
            or isinstance(seal_id, bool)
            or seal_id < 1
        ):
            return False, "invalid seal ID"

        # Step 2: Retrieve the device-specific secret key.
        try:
            secret_key = get_device_key(seal_id)
        except ValueError:
            return False, "device authentication key unavailable"

        # Step 3: Authenticate the packet before updating replay state.
        if not verify_hmac(packet, secret_key, received_hmac):
            return False, "message authentication failed"

        # Step 4: Validate the event sequence.
        return self.replay_protector.check_sequence(
            seal_id,
            sequence,
        )