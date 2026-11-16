"""Errors crossing application/adapter boundaries."""


class OperationCancelled(Exception):
    """The user cancelled a background operation."""


class AudioDeviceError(RuntimeError):
    """The audio device could not be initialized."""
