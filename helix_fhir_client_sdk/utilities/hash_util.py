import hashlib


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
