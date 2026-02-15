import os
import queue
import threading
import zipfile
from typing import Generator, Optional


class _ZipStreamAdapter:
    """
    A file-like object that writes data to a queue.
    Used to bridge zipfile's write operations to a generator.
    """

    def __init__(self, q: queue.Queue):
        self.q = q
        self.pos = 0

    def write(self, b: bytes) -> int:
        self.q.put(b)
        self.pos += len(b)
        return len(b)

    def tell(self) -> int:
        return self.pos

    def flush(self) -> None:
        pass

    def seekable(self) -> bool:
        return False


class StreamableZip:
    """
    Generates a ZIP file on-the-fly from a directory.

    Usage:
        streamer = StreamableZip(directory_path)
        for chunk in streamer:
            socket.send(chunk)
    """

    def __init__(self, directory_path: str):
        self.directory_path = directory_path
        # Use a small buffer size to keep memory usage low but avoid excessive context switching
        self.queue: queue.Queue = queue.Queue(maxsize=32)
        self.finished = False
        self.exception: Optional[Exception] = None
        self._thread: Optional[threading.Thread] = None

    def __iter__(self) -> Generator[bytes, None, None]:
        if self._thread is None:
            self._thread = threading.Thread(target=self._generate_zip)
            self._thread.daemon = True
            self._thread.start()

        while True:
            try:
                # Wait for data with a timeout to allow checking for thread death
                chunk = self.queue.get(timeout=0.1)
                yield chunk
            except queue.Empty:
                if self.finished:
                    # If finished and queue is empty, we are done
                    break
                if not self._thread.is_alive():
                    # Thread died unexpectedly without setting finished (shouldn't happen due to finally)
                    # But if it did, we must stop.
                    if self.exception:
                        raise self.exception
                    break
                continue

            # Check for exceptions from the thread
            if self.exception:
                raise self.exception

    def _generate_zip(self) -> None:
        try:
            stream = _ZipStreamAdapter(self.queue)

            # allowZip64=True is required for non-seekable streams
            with zipfile.ZipFile(
                stream, "w", zipfile.ZIP_DEFLATED, allowZip64=True
            ) as zf:
                for root, _, files in os.walk(self.directory_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Calculate archive name relative to the base directory
                        archive_name = os.path.relpath(file_path, self.directory_path)
                        try:
                            zf.write(file_path, archive_name)
                        except (OSError, PermissionError):
                            # Skip files we can't read
                            pass
        except Exception as e:
            self.exception = e
        finally:
            self.finished = True
