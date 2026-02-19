> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fal.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Core Concepts

> Understanding these essential terms will help you follow the tutorials and deploy your first model successfully.

## App

An **App** is a Python class that wraps your AI model for deployment. Your app defines what packages it needs, how to load your model, and how users interact with it.

```python  theme={null}
class MyApp(fal.App):
    machine_type = "GPU-H100"  # Choose your hardware

    def setup(self):
        # Load your model here
        # Executed on each runner

    @fal.endpoint("/")
    def generate(self, input_data):
        # Your endpoint logic here—usually a model call

    def teardown(self):
        # Cleanup code here
        # Executed on each runner when the runner is shutting down
```

## Where Code Runs: Local vs Remote Execution

### What runs locally

* Module import / top level: When Python imports your file, all top-level code executes on your machine.

* This is where you typically define helpers, constants, and construct objects you might pass to the app.

* Building the app object: The class body for your app is defined locally (like any Python class).

* Serialization boundary preparation: When you reference local objects from the app (e.g., myobj), we attempt to pickle them locally to ship to the remote runtime.

### What runs remotely

* Class transfer & instantiation: Your fal.App subclass is **pickled locally**, then **unpickled and instantiated remotely** in the runtime you configured (e.g. requirements, container image, etc.).

* App methods / entrypoints: Methods of your app class (e.g. `setup`, `@fal.endpoint`s, etc) execute on the remote machine.

* Referenced symbols:
  * Pickled objects (closures, small data, simple classes) are shipped as part of the app payload.
  * Importable code (installed packages or modules present in the remote image) is imported remotely instead of being shipped.

### Example

```python  theme={null}
# --- Local (import-time) ---
import os
import fal
import json

# Local constant (pickled if referenced).
# Environment variable comes from the local environment.
CONFIG = {"myparameter": os.environ["MYPARAMETER"]}

# Local helper (pickled by definition if referenced - code is not executed locally).
def myhelper(x):
    # Runs remotely
    import mylib
    return mylib.helper(x)

class MyApp(fal.App):
    def setup(self):
        # Runs remotely once on each runner
        # Load deps from remote environment (fast, deterministic)
        import mylib  # must be installed in remote image/requirements or dynamically installed before this line
        self.pipeline = mylib.load_pipeline()

    @fal.endpoint("/")
    def generate(self, input: MyInput) -> MyOutput:
        # Runs remotely on each request
        result = self.pipeline(input, k=CONFIG["MYPARAMETER"])
        return MyOutput(result)

    def teardown(self):
        # Runs remotely on each runner when the runner is shutting down
        self.pipeline.close()
```

## Lifespan

### Startup

#### `setup()`

When a runner starts, it first initializes the application and calls the `setup()` method. This is where you should load your model, initialize connections, and prepare any resources needed to serve requests. The runner is not considered ready until `setup()` completes successfully.

### Shutdown

Runners can be terminated for several reasons:

* **Expiration**: Runners will be terminated when they reach their expiration time
* **Manual stop/kill**: You can manually terminate runners using the CLI or dashboard
* **Scaling activity**: Runners may be terminated when scaling down due to reduced demand

When a runner is requested to terminate, it receives a `SIGTERM` signal. After receiving `SIGTERM`, no new requests are routed to the runner, and it has **5 seconds** to:

1. Run `handle_exit()` (if defined)
2. Finish processing ongoing requests
3. Run `teardown()` for cleanup

After this grace period, the runner is forcefully terminated with a `SIGKILL`.

<Warning>
  If you are using `fal<1.61.0`, runners will be terminated immediately without a grace period.
</Warning>

#### `handle_exit()`

The `handle_exit()` method is called immediately when a `SIGTERM` is received. Use this to signal your request handlers to stop processing early, so there's enough time remaining for cleanup in `teardown()`.

Without `handle_exit()`, long-running requests may consume the entire grace period, causing `teardown()` to be skipped when `SIGKILL` arrives.

#### `teardown()`

The `teardown()` method is called after all ongoing requests have finished. Use this to clean up resources, close connections, or perform any final operations before the runner terminates.

<Note>
  While it's possible to add your own signal handlers, we recommend using `handle_exit()` instead.
  The `setup()`, `handle_exit()`, and `teardown()` methods provide a clean and predictable way to manage your application's lifecycle without the complexity of custom signal handling.
</Note>

### Example

```python  theme={null}
class MyApp(fal.App):
    def setup(self):
        # Called when runner starts
        self.model = load_model()
        self.db = connect_to_database()
        self.exit = threading.Event()

    @fal.endpoint("/")
    def run(self, input: Input) -> Output:
        for i in range(30):
            if self.exit.is_set():
                # SIGTERM received, stop processing early
                break
            # Do some work here
        return Output(result=result)

    def handle_exit(self):
        # Called when runner is exiting (SIGTERM)
        self.exit.set()

    def teardown(self):
        # Called when runner shuts down
        self.db.close()
```

## Retry Policy

When using the [queue](/model-apis/model-endpoints/queue), fal automatically retries requests in the following scenarios:

* **Server Error**: The connection with the app broke or the runner returned a `503` status code
* **Timeout**: The  app took longer to respond than the request timeout or the runner returned a `504` status code

By default, fal retries in all these situations.

### Control Retry Behavior

You can configure your app to skip retries for specific conditions using the `skip_retry_conditions` option.
Available conditions are `"server_error"` and `"timeout"`.

```python  theme={null}
class MyApp(fal.App):
    skip_retry_conditions=["timeout"]  # This app won't retry on timeout
    ...
```

For per-request control, see [Model APIs docs](/model-apis/model-endpoints/reliability#disabling-retries-per-request).

### Override Retry Behavior Per Response

You can override the default retry behavior on a per-response basis by returning the `X-Fal-Needs-Retry` header from your endpoint. This gives your application explicit control over whether a request should be retried, **independent of the HTTP status code**.

| Header Value | Behavior                                                              |
| ------------ | --------------------------------------------------------------------- |
| `1`          | Force a retry, even if the status code would normally not trigger one |
| `0`          | Prevent a retry, even if the status code would normally trigger one   |

```python  theme={null}
import fal
from fastapi.responses import JSONResponse

class MyApp(fal.App):
    @fal.endpoint("/")
    def run(self, input: Input) -> Output:
        try:
            result = self.model.run(input)
            return result
        except TransientError:
            # Signal that this request should be retried
            return JSONResponse(
                status_code=500,
                headers={"X-Fal-Needs-Retry": "1"},
                content={"detail": "Transient error, please retry"},
            )
        except NonRetryableError:
            # Signal that this request should NOT be retried
            return JSONResponse(
                status_code=503,
                headers={"X-Fal-Needs-Retry": "0"},
                content={"detail": "Non-retryable error"},
            )
```

<Note>
  The `X-Fal-Needs-Retry` header takes precedence over the default [status code-based retry logic](/serverless/reliability/readiness-liveness#ongoing). For example, returning a `503` with `X-Fal-Needs-Retry: 0` will prevent the retry that would normally occur for a `503`.
</Note>

## Machine Type

**Machine Type** specifies the hardware (CPU or GPU) your app runs on. Choose based on your model's needs: `"CPU"` for lightweight models, `"GPU-H100"` for most AI models, or `"GPU-B200"` for large models.

## Runner

A **Runner** is a compute instance that executes your app using your chosen machine type. Runners automatically start when requests arrive and shut down when idle to save costs.

## Endpoint

An **Endpoint** is a function in your app that users can call via API. It defines how your model processes inputs and returns outputs.

### Playground

Each endpoint gets an automatic **Playground** - a web interface where you can test your model with different inputs before integrating it into your application.

## `fal run` vs `fal deploy`

* **`fal run`**: Test your app on a single cloud GPU during development. Creates a temporary URL that disappears when you stop the command. Defaults to `public` auth (no authentication required).

* **`fal deploy`**: Deploy your app to production. Creates a permanent URL that stays available until you delete it. Defaults to `private` auth (API key required).

Both commands support the `--auth` flag to control access:

* `--auth public`: Anyone can call your app without authentication (you pay for usage)
* `--auth private`: Requires API key authentication

Use `fal run` while building and testing, then `fal deploy` when ready for production use.

## Next Steps

<CardGroup cols={2}>
  <Card title="Manage Dependencies" icon="box" href="/serverless/getting-started/manage-dependencies">
    Install pip packages, prebuilt wheels, and private packages
  </Card>

  <Card title="Deploy to Production" icon="rocket" href="/serverless/deployment-operations/deploy-to-production">
    Deploy your app and manage production releases
  </Card>
</CardGroup>
