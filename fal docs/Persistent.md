> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fal.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Use Persistent Storage

> Each fal app runner runs in an isolated environment that gets voided when the runner is released. This includes wiping the filesystem except for the persistent `/data` volume. This volume is an eventually-consistent distributed file system that is mounted on each runner, across all your apps running at any point in time, linked to your fal account. You can use this volume to persist data across requests, runners and apps. For example, to cache a torchvision dataset in your app, you can do the following:

```python  theme={null}
import fal
from pathlib import Path

DATA_DIR = Path("/data/mnist")

class FalModel(fal.App):
    requirements = ["torch>=2.0.0", "torchvision"]
    machine_type = "GPU"

    def setup(self):
        import torch
        from torchvision import datasets

        already_present = DATA_DIR.exists()
        if already_present:
            print("Test data is already downloaded, skipping download!")

        test_data = datasets.FashionMNIST(
            root=DATA_DIR,
            train=False,
            download=not already_present,
        )
        ...
```

When you invoke this app for the first time, you will notice that Torch downloads the test dataset. However, subsequent invocations - even those not covered by the invocation's `keep_alive` - will skip the download and proceed directly to your logic.

<Note>
  **Implementation note**

  For HF-related libraries, fal ensures all downloaded models are persisted to
  avoid re-downloads when running ML inference workloads. No need to customize
  the output path for `transformers` or `diffusers`.
</Note>

## Usage Considerations

Since the `/data` is a distributed filesystem, there are a couple of caveats to keep in mind.

### Concurrency

`/data` is shared across all runners, so you should be mindful of how you access common files from your runners to avoid race conditions. For example, when creating or
downloading a file, you should use a temporary unique path beside the final destination until the file is fully downloaded or created and only then move it into place,
which makes the operation quasi-atomic and avoids the situation where another runner tries to use an incomplete file.

```python  theme={null}
import fal
import tempfile
import os
from pathlib import Path

WEIGHTS_URL = "https://example.com/weights.safetensors"
WEIGHTS_FILE = Path("/data/weights.safetensors")


class FalModel(
    fal.App,
    ...,
):
    def setup(self):
        # Create temporary file right beside the final destination, so that we can
        # use os.rename to move the file into place with 1 system call within the
        # same filesystem.
        with tempfile.NamedTemporaryFile(delete=False, dir="/data") as temp_file:
            # download the weights
            ...
            # Move the weights to the final destination.
            os.rename(temp_file.name, WEIGHTS_FILE)
        ...
```

### Sequential vs parallel reading

Avoid reading multiple files sequentially, especially if they are small. Sequential reads do not take full advantage of the massively parallel caching and downloading capabilities of the file system.

Total throughput is always higher when multiple files are read in parallel.

If the process of loading model weights into memory is sequential, you can greatly speed it up by pre-reading all the files with code like this:

```sql  theme={null}
MODEL_DIR = "/data/models/deepseek-ai"

subprocess.check_call(
    f"find '{MODEL_DIR}' -type f | "
    "xargs -P 32 -I {} cat {} > /dev/null",
    shell=True
)
```

## Filesystem internals

### Persistence

Each file is split into 4MB chunks (identified by their hash) which are saved into a global object store. A metadata layer stores the relation between file paths and chunks, ensuring that non-content operations (e.g. renames) are atomic and fast.

### Caching

The `/data` volume features 2 caching layers:

* Local cache on the node (RAID 5 on NVME drives). Typical speeds are 10-15 GB/s. A cache miss falls through to the distributed cache.
* Distributed cache amongst all servers in the local datacenter, where chunks are evenly distributed. Access is typically very fast, using a 100 GBps network. Typical speeds are 6-8 GB/s. A cache miss falls through to the object store.

This is what happens during a file read:

1. The metadata service is consulted to obtain the chunk IDs linked to the file path
2. The file system tries to find the chunks in the local cache. Available chunks are directly read.
3. On cache miss, the distributed cache is tried. Available chunks are streamed in parallel (from multiple nodes) and also saved into the local cache.
4. On distributed cache miss, the missing chunks are downloaded from the backing object store by the individual nodes responsible for each chunk.
   Typical speeds are 1.5-8 GB/s depending on datacenter size and number of chunks.
   The target server synchronously streams the chunks to its local cache as they are fetched.
   If the chunks are not available in the object store, the read operation blocks until they appear. This likely means that the file was written recently and the source server is still uploading data (see below).

This is what happens during a file write:

1. While a file is being written, it is buffered in memory/local disk (already in chunks).
2. When the file is closed, the chunks are moved to the local cache and are written to the metadata layer. At this point, another process on the same server can access the file.
3. The server starts sharing the chunks with the other members of the distributed cache. Once this is done, the file is available to other servers in the same datacenter.
4. In parallel to the above, the server also starts uploading the chunks in the background to the object store. Speeds are typically 300-500 MB/s. Once the upload is done, the file is available to all data centers.

## Alternative: KVStore for Small Key-Value Data

For storing small pieces of state (configuration, cached API responses, session data), fal also provides [KVStore](/serverless/development/use-kv-store) - a simple key-value storage with zero setup. KVStore is designed for data up to 25 MB per value and provides faster access for small data compared to file-based storage.

Use `/data` for large files and model weights. Use KVStore for small configuration and state data.
