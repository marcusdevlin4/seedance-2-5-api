"""Checks openapi.yaml without any network access:

* the document parses and every internal $ref points at something,
* every example body in examples/ is a valid Seedance 2.5 request,
* requests the API is documented to reject are rejected by the schema too,
* the job examples match the Job schema.

    pip install pytest pyyaml jsonschema
    pytest
"""
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load((ROOT / "openapi.yaml").read_text())


def validator(name):
    """A validator for one component schema; local $refs resolve inside the spec."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"#/components/schemas/{name}",
        "components": SPEC["components"],
    }
    return Draft202012Validator(schema)


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def test_document_shape():
    assert SPEC["openapi"] == "3.1.0"
    assert SPEC["servers"] == [{"url": "https://argolink.io"}]
    operations = {
        (path, method): op["operationId"]
        for path, item in SPEC["paths"].items()
        for method, op in item.items()
    }
    assert operations == {
        ("/v1/videos/generations", "post"): "createVideoGeneration",
        ("/v1/videos/{request_id}", "get"): "getVideoGeneration",
        ("/v1/videos/{request_id}/content", "get"): "downloadVideoContent",
        ("/v1/media/uploads", "post"): "createMediaUpload",
        ("/v1/models", "get"): "listModels",
    }
    assert SPEC["paths"]["/v1/models"]["get"]["security"] == []


def test_every_internal_ref_resolves():
    for node in walk(SPEC):
        ref = node.get("$ref")
        if not ref:
            continue
        assert ref.startswith("#/"), ref
        target = SPEC
        for part in ref[2:].split("/"):
            assert part in target, f"dangling {ref}"
            target = target[part]


def test_job_statuses_are_the_documented_four():
    status = SPEC["components"]["schemas"]["Job"]["properties"]["status"]
    assert status["enum"] == ["pending", "done", "failed", "expired"]


EXAMPLE_FILES = sorted((ROOT / "examples").glob("*.json"))


def test_spec_lists_every_example_file():
    content = SPEC["paths"]["/v1/videos/generations"]["post"]["requestBody"]["content"]
    listed = {ex["externalValue"] for ex in content["application/json"]["examples"].values()}
    assert listed == {f"examples/{path.name}" for path in EXAMPLE_FILES}


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda p: p.name)
def test_example_bodies_are_valid(path):
    body = json.loads(path.read_text())
    errors = [e.message for e in validator("GenerationRequest").iter_errors(body)]
    assert errors == []


BASE = {"model": "seedance-2.5", "prompt": "a lighthouse in a storm"}
IMAGE = {"url": "https://example.com/a.png"}
VIDEO = {"url": "https://example.com/a.mp4"}

REJECTED = {
    "seed is not supported": {**BASE, "seed": 7},
    "watermark true": {**BASE, "watermark": True},
    "31 seconds": {**BASE, "duration": 31},
    "3 seconds": {**BASE, "duration": 3},
    "4k is a 2.0-only tier": {**BASE, "resolution": "4k"},
    "two videos per request": {**BASE, "n": 2},
    "missing prompt": {"model": "seedance-2.5", "duration": 5},
    "plain http asset": {**BASE, "reference_images": [{"url": "http://example.com/a.png"}]},
    "31 reference images": {**BASE, "reference_images": [IMAGE] * 31},
    "end frame without start frame": {**BASE, "aspect_ratio": "adaptive", "end_image": IMAGE},
    "frame plus references": {**BASE, "aspect_ratio": "adaptive", "start_image": IMAGE, "reference_images": [IMAGE]},
    "fixed ratio in a frame mode": {**BASE, "aspect_ratio": "16:9", "start_image": IMAGE},
    "adaptive on text to video": {**BASE, "aspect_ratio": "adaptive"},
    "edit with an image": {**BASE, "omni_reference_task_type": "edit", "reference_videos": [VIDEO], "reference_images": [IMAGE]},
    "edit with two videos": {**BASE, "omni_reference_task_type": "edit", "reference_videos": [VIDEO, VIDEO]},
    "edit with a fixed length": {**BASE, "omni_reference_task_type": "edit", "reference_videos": [VIDEO], "duration": 5},
    "extend is not supported": {**BASE, "omni_reference_task_type": "extend", "reference_videos": [VIDEO]},
    "unknown field": {**BASE, "callback_url": "https://example.com/hook"},
}


@pytest.mark.parametrize("body", REJECTED.values(), ids=REJECTED.keys())
def test_documented_rejections(body):
    assert list(validator("GenerationRequest").iter_errors(body)), "schema accepted a request the API rejects"


ACCEPTED = {
    "prompt only": BASE,
    "edit may send -1 and adaptive": {**BASE, "omni_reference_task_type": "edit", "reference_videos": [VIDEO], "duration": -1, "aspect_ratio": "adaptive"},
    "fal field names": {**BASE, "image_urls": ["https://example.com/a.png"], "seconds": 6, "ratio": "1:1"},
    "size instead of resolution": {**BASE, "size": "1280x720"},
    "silent video": {**BASE, "generate_audio": False, "n": 1, "watermark": False},
}


@pytest.mark.parametrize("body", ACCEPTED.values(), ids=ACCEPTED.keys())
def test_documented_acceptances(body):
    assert [e.message for e in validator("GenerationRequest").iter_errors(body)] == []


@pytest.mark.parametrize("name", ["PendingJob", "DoneJob", "FailedJob"])
def test_job_examples_match_schema(name):
    value = SPEC["components"]["examples"][name]["value"]
    assert [e.message for e in validator("Job").iter_errors(value)] == []


def test_done_job_bills_output_plus_reference_seconds():
    usage = SPEC["components"]["examples"]["DoneJob"]["value"]["usage"]
    assert usage["billed_seconds"] == usage["output_seconds"] + usage["reference_video_seconds"]
