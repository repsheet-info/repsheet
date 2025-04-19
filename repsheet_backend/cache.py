import traceback
from typing import Any, Callable, Literal, Optional, Protocol

from google.cloud import storage
from google.cloud.storage.blob import BlobWriter
from google.cloud.exceptions import NotFound

import asyncio
import hashlib
import lzma
import pickle
from base64 import urlsafe_b64encode
from functools import wraps
from typing import Any
import orjson

CacheKey = str | dict[str, Any]
"""
A cache key can be either a string or a dictionary of attributes.
If a dictionary is used, the key will be generated using cache_key to hash the object.
"""


def cache_key(key_obj: Any) -> tuple[str, bytes]:
    """
    Returns a cache key and a JSON representation of the key object.
    """
    # sort keys to ensure determinism
    as_json = orjson.dumps(key_obj, option=orjson.OPT_SORT_KEYS)
    sha_bytes = hashlib.md5(as_json).digest()
    return urlsafe_b64encode(sha_bytes).decode().strip("="), as_json


def pickle_and_compress(value: Any) -> bytes:
    return lzma.compress(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))


def dump_json_and_compress(value: Any) -> bytes:
    return lzma.compress(orjson.dumps(value))


def decompress_and_unpickle(data: bytes) -> Any:
    return pickle.loads(lzma.decompress(data))


def decompress_and_load_json(data: bytes) -> Any:
    return orjson.loads(lzma.decompress(data))


class GCSCache:
    """Simple caching mechanism using pickle and Google Cloud Storage.
    Cache keys can be any JSON serializable object, and values can be anything pickleable.
    """

    mode: Literal["pickle", "json"]
    cache_bucket: str
    key_prefix: str

    def __init__(
        self,
        project: str,
        cache_bucket: str,
        key_prefix: str = "",
        mode: Literal["pickle", "json"] = "pickle",
    ):
        self.cache_bucket = cache_bucket
        self.gcs = storage.Client(project=project)
        self.bucket = self.gcs.bucket(self.cache_bucket)
        self.key_prefix = key_prefix
        self.mode = mode

    def _has_sync(self, key: CacheKey) -> bool:
        if not isinstance(key, str):
            key, _ = cache_key(key)
        key = f"{self.key_prefix}{key}"
        if self.mode == "json":
            blob = self.bucket.blob(f"{key}/data.json.xz")
        else:
            blob = self.bucket.blob(f"{key}/data.pickle.xz")
        return blob.exists()

    def _set_sync(self, key: CacheKey, value: Any):
        if not isinstance(key, str):
            key, key_json = cache_key(key)
        else:
            key_json = None
        key = f"{self.key_prefix}{key}"
        if self.mode == "json":
            blob = self.bucket.blob(f"{key}/data.json.xz")
            data = dump_json_and_compress(value)
        else:
            blob = self.bucket.blob(f"{key}/data.pickle.xz")
            data = pickle_and_compress(value)
        with BlobWriter(blob) as f:
            f.write(data)
        if key_json is not None:
            json_blob = self.bucket.blob(f"{key}/key.json")
            with BlobWriter(json_blob) as f:
                f.write(key_json)

    def _get_sync(self, key: CacheKey) -> Any:
        try:
            if not isinstance(key, str):
                key, _ = cache_key(key)
            key = f"{self.key_prefix}{key}"

            if self.mode == "json":
                blob = self.bucket.blob(f"{key}/data.json.xz")
                data = blob.download_as_bytes()
                data = decompress_and_load_json(data)
            else:
                blob = self.bucket.blob(f"{key}/data.pickle.xz")
                data = blob.download_as_bytes()
                data = decompress_and_unpickle(data)

            return data
        except NotFound:
            return None
        
    def cache_key(self, key_obj: Any) -> str:
        """
        Returns the cache key used for a given object.
        """
        return cache_key(key_obj)[0]

    async def init(self):
        """Checks if we can connect to the bucket. Doesn't actually "initialize" anything per se."""
        await asyncio.to_thread(self.bucket.reload)

    async def set(self, key: CacheKey, value: Any):
        """Set a value in the cache.

        Args:
            key: The key to use for the cache entry. If not a string, the key will be generated using cache_key.
            value: The value to store in the cache.
        """
        await asyncio.to_thread(self._set_sync, key, value)

    def set_nowait(self, key: CacheKey, value: Any):
        asyncio.create_task(self.set(key, value))

    async def get(self, key: CacheKey) -> Any:
        """Get a value from the cache.

        Args:
            key: The key to use for the cache entry. If not a string, the key will be generated using cache_key.
        """
        return await asyncio.to_thread(self._get_sync, key)

    async def has(self, key: CacheKey) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: The key to use for the cache entry. If not a string, the key will be generated using cache_key.
        """
        return await asyncio.to_thread(self._has_sync, key)

    def cache_async_function(self, get_key: Optional[Callable] = None):
        """Decorator to cache the return value of an async function.

        Args:
            get_key: A function that takes the same arguments as the decorated function and returns a `CacheKey`.
                If None, a default key will be generated from the function name, filename, and arguments.
        """

        def decorator(async_func):
            @wraps(async_func)
            async def wrapper(*args, **kwargs):
                if get_key is not None:
                    key = get_key(*args, **kwargs)
                else:
                    key = dict(
                        name=async_func.__name__,
                        location=async_func.__code__.co_filename,
                        args=args,
                        kwargs=kwargs,
                    )
                result = await self.get(key)
                if result is None:
                    result = await async_func(*args, **kwargs)
                    self.set_nowait(key, result)
                return result

            return wrapper

        return decorator
