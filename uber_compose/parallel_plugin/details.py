import base64

from vedro.core import FileArtifact
from vedro.core import MemoryArtifact


def serialize_artifact(artifact) -> dict:
    if isinstance(artifact, MemoryArtifact):
        return {
            'kind': 'memory',
            'name': artifact.name,
            'mime': artifact.mime_type,
            'data': base64.b64encode(artifact.data).decode(),
        }
    if isinstance(artifact, FileArtifact):
        return {
            'kind': 'file',
            'name': artifact.name,
            'mime': artifact.mime_type,
            'path': str(artifact.path),
        }
    return {'kind': type(artifact).__name__}


def _stream_value(stream) -> str:
    getter = getattr(stream, 'get_value', None)
    if getter is None:
        return str(stream)
    return getter()


def serialize_captured_output(captured_output) -> dict | None:
    if captured_output is None:
        return None
    return {
        'stdout': _stream_value(captured_output.stdout),
        'stderr': _stream_value(captured_output.stderr),
    }


def serialize_result_details(result) -> dict:
    return {
        'artifacts': [serialize_artifact(artifact) for artifact in result.artifacts],
        'captured_output': serialize_captured_output(result.captured_output),
        'extra_details': list(result.extra_details),
        'steps': [
            {
                'name': step.step_name,
                'artifacts': [serialize_artifact(artifact) for artifact in step.artifacts],
                'captured_output': serialize_captured_output(step.captured_output),
                'extra_details': list(step.extra_details),
            }
            for step in result.step_results
        ],
    }


__all__ = ("serialize_artifact", "serialize_captured_output", "serialize_result_details",)
