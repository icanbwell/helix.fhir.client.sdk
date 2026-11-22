import hashlib
import json

from compressedfhir.fhir.fhir_resource import FhirResource


class ResourceHash:
    def __init__(self, hash_algorithm: str = "sha256") -> None:
        # Set the hash algorithm
        self.hash_algorithm = hash_algorithm.lower()

    def hash_value(self, value: str) -> str:
        # Hash a value using the specified algorithm
        if self.hash_algorithm not in hashlib.algorithms_available:
            raise ValueError(f"Hash algorithm {self.hash_algorithm} is not supported.")
        hasher = hashlib.new(self.hash_algorithm)
        hasher.update(value.encode("utf-8"))
        return hasher.hexdigest()


def stable_resource_hash_input(resource: FhirResource) -> str:
    """
    The text that ``raw_hash`` values are computed from.

    Callers may have persisted these hashes, so the text must not change when the client's
    ``byte_identical_json`` option does.  The resource is therefore always written with
    ``byte_identical=True`` (the text compressedfhir 3.0.5 wrote) and normalized with the
    standard library, whatever the client mode.
    """
    return json.dumps(json.loads(resource.json(byte_identical=True)), sort_keys=True)
