"""Contract proofs for renderer-independent MonoForm normalization."""

from unittest import TestCase

from fastapi import FastAPI
from pydantic import BaseModel

from monotools.runtime.monoform import (
    MonoFormContractError, monoform_manifest, monoform_operation,
)


class Example(BaseModel):
    name: str
    count: int | None = None
    tags: list[str] = []


class MonoFormContractTests(TestCase):
    def _schema(self) -> dict:
        app = FastAPI()

        @app.post("/api/examples", operation_id="create_example",
            openapi_extra=monoform_operation(kind="create", entity="example",
                title="Create example", submit_label="Save"))
        async def create(value: Example) -> Example:
            return value

        return app.openapi()

    def test_normalizes_refs_nullable_arrays_and_stable_identity(self) -> None:
        manifest = monoform_manifest(self._schema(), app="sample", title="Sample")
        operation = manifest["operations"][0]
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(operation["operationId"], "create_example")
        self.assertEqual(operation["bodySchema"]["properties"]["count"]["nullable"], True)
        self.assertEqual(operation["bodySchema"]["properties"]["tags"]["items"]["type"], "string")
        self.assertEqual(manifest, monoform_manifest(self._schema(), app="sample", title="Sample"))

    def test_rejects_unsupported_composition_at_exact_location(self) -> None:
        schema = self._schema()
        schema["components"]["schemas"]["Example"]["properties"]["name"] = {
            "oneOf": [{"type": "string"}, {"type": "integer"}],
        }
        with self.assertRaisesRegex(MonoFormContractError,
            r"requestBody.*properties.name.oneOf is not supported"):
            monoform_manifest(schema, app="sample", title="Sample")

    def test_declaration_rejects_blank_public_labels(self) -> None:
        with self.assertRaisesRegex(MonoFormContractError, "title must be a non-empty string"):
            monoform_operation(kind="create", entity="example", title="", submit_label="Save")

    def test_rejects_non_api_paths(self) -> None:
        schema = self._schema()
        schema["paths"]["/outside"] = schema["paths"].pop("/api/examples")
        with self.assertRaisesRegex(MonoFormContractError, "same-origin /api path"):
            monoform_manifest(schema, app="sample", title="Sample")
