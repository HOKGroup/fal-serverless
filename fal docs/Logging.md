> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fal.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Logging

> Learn how logs are captured in fal serverless apps, and how to use print statements or Python's logging module effectively.

Logging helps you debug your app during local development and after deployment.

In fal serverless, anything your app writes to `stdout` or `stderr` is captured in runner logs.

## Runner Logs vs Request Logs

* **Runner logs** are logs produced by a runner process over its lifetime (startup, setup, and request handling).
* **Request logs** are the portion of runner logs emitted while a specific request is being processed.

<Note>
  Request logs (the logs visible to an end user for a request) are a time-scoped subset of runner logs.
</Note>

## Basic Logging with `print`

For quick debugging, `print()` is enough:

```python  theme={null}
import fal
import sys

class MyApp(fal.App):
    @fal.endpoint("/")
    def run(self) -> dict:
        print("Processing Hello World request...")
        print("Cache miss, loading resources", file=sys.stderr)
        return {"message": "Hello, World!"}
```

Both messages are captured in logs because both `stdout` and `stderr` are collected.

## Application Logging with Python `logging`

For production apps, use Python's standard `logging` module so you can control log levels and message format.

```python  theme={null}
import logging
import fal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("my_app")

class MyApp(fal.App):
    @fal.endpoint("/")
    def run(self) -> dict:
        logger.info("Started request processing")
        try:
            # Your application logic
            result = {"message": "Hello, World!"}
            logger.info("Request completed successfully")
            return result
        except Exception:
            logger.exception("Request failed")
            raise
```

<Tip>
  Avoid logging secrets, API keys, or large raw payloads. Log IDs, sizes, and high-level status instead.
</Tip>

## Log Sources

When filtering logs by `source`, you'll commonly see:

* `run`: logs from runners created by [`fal run`](/reference/cli/run)
* `gateway`: logs from runners serving deployed apps
* `deploy`: logs emitted by the deployment process itself when using [`fal deploy`](/reference/cli/deploy)

## Where to View Logs

* In the [fal dashboard](https://fal.ai/dashboard/logs), with filters for runner ID, request ID, version ID and source
* In the CLI with [`fal runners logs <runner-id>`](/reference/cli/runners)
* In request-level log views for each request
* In Model APIs via the [Queue API](/model-apis/model-endpoints/queue) for request-level logs
