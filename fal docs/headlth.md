> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fal.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Add Health Check Endpoint

> Add a health check endpoint to your fal app to check if the runner is healthy.

Health check endpoints allow fal to verify that your runners are functioning correctly. When a health check fails, fal will automatically terminate the unhealthy runner and spin up a new one.

## Basic Usage

Use the `health_check` parameter in the `@fal.endpoint()` decorator to configure an endpoint as your health check:

```python  theme={null}
import fal
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str

class MyApp(fal.App):
    def setup(self):
        self.model = load_model()
        self.connection = connect_to_something()
    
    @fal.endpoint("/")
    def predict(self, input: Input) -> Output:
        x = self.connection.do_something(input)
        return self.model.run(x)

    @fal.endpoint(
        "/health",
        health_check=fal.HealthCheck(
            start_period_seconds=10,
            timeout_seconds=5,
            failure_threshold=3,
            call_regularly=True,
        ),
    )
    def health(self) -> HealthResponse:
        if not self.connection.is_alive():
            raise RuntimeError("Lost connection to the external service")
        return HealthResponse(status="ok")
```

<Note>
  Only one endpoint can be designated as the health check endpoint per app.
</Note>

### Health Check Configuration

| Parameter              | Type | Description                                                                                                  | Default |
| ---------------------- | ---- | ------------------------------------------------------------------------------------------------------------ | ------- |
| `start_period_seconds` | int  | Minimum time the runner has been running before considering the runner unhealthy when health check fails.    | `30`    |
| `timeout_seconds`      | int  | Timeout in seconds for the health check request.                                                             | `5`     |
| `failure_threshold`    | int  | Number of consecutive failures before considering the runner as unhealthy.                                   | `3`     |
| `call_regularly`       | bool | Perform health check every 15s. If false, only do it when the `x-fal-runner-health-check` header is present. | `True`  |

<Note>
  To prevent the health check from failing too early, `start_period_seconds` will be replaced by `startup_timeout` of the application if it's less than it.
</Note>

### Signaling Unhealthy State

To signal that a runner is unhealthy, **raise an exception** inside your health check endpoint. When fal receives an error response from the health check, it marks the runner as unhealthy.

```python  theme={null}
@fal.endpoint("/health", health_check=fal.HealthCheck(failure_threshold=3))
def health(self) -> HealthResponse:
    if not self.connection.is_alive():
        raise RuntimeError("Lost connection to the external service")
    return HealthResponse(status="ok")
```

## Automatic Health Checks

Health checks are performed automatically every 15 seconds.
Automatic health checks are enabled by default. You can disable them by setting `call_regularly` to `False`.

1. **Registration**: The endpoint with `health_check` parameter set is registered as the health check endpoint for your app.
2. **Start period**: Health check failures are ignored if the runner has been running for less than `start_period_seconds` seconds.
3. **Periodic checks**: fal periodically (every 15 seconds) calls this endpoint to verify runner health.
4. **Automatic recovery**: If the health check fails or times out for `failure_threshold` consecutive calls, the runner is terminated and replaced.

<Warning>
  The health check endpoint can be called while there might be another request running.

  Please avoid heavy computations or acquiring critical resources such as GPUs in the health check endpoint
  and make sure it does not interfere with the other actual requests.
</Warning>

## Manual Health Checks

You can request a health check manually by setting the `x-fal-runner-health-check` header in your regular endpoints.

```python  theme={null}
@fal.endpoint("/predict")
def predict(self, input: Input, response: Response) -> Output:
    response.headers["x-fal-runner-health-check"] = "true"
    return self.model.run(input)
```

Manually requested health checks ignores the `failure_threshold` and the `start_period_seconds`.
The runner will be terminated immediately if the manual health check fails.

## Guidelines

### Avoid using GPUs and keep it lightweight

The health check endpoint can be called while there might be another request running.
To make sure it does not interfere with the other actual requests, health checks should be fast and not consume significant resources.

Please avoid running inference, heavy computations or acquiring critical resources such as GPUs in your health check endpoint.

```python  theme={null}
# Good: Simple status check
@fal.endpoint("/health", fal.HealthCheck(timeout_seconds=10))
def health(self) -> HealthResponse:
    if not self.connection.is_alive():
        raise RuntimeError("Lost connection to the external service")
    return HealthResponse(status="ok")

# Avoid: Running inference in health check
@fal.endpoint("/health", fal.HealthCheck(timeout_seconds=10))
def health(self) -> HealthResponse:
    # Don't do this - it's slow and wastes GPU cycles, it might interfere with the other requests
    test_output = self.model.run(test_input)
    return HealthResponse(status="ok")
```

If you are still concerned about the performance impact of the health check, you can set `call_regularly` to `False` and request a health check manually by setting the `x-fal-runner-health-check` header in your regular endpoints.
See [Request for Health Check](#request-for-health-check) for details.

### Raise exceptions for critical failures only

To avoid unnecessary runner replacements, only raise exceptions for truly unhealthy states that require runner replacement. For non-critical issues, consider logging instead.

```python  theme={null}
@fal.endpoint("/health", fal.HealthCheck(timeout_seconds=10))
def health(self) -> HealthResponse:
    if not self.connection.is_alive():
        print("Warning: Connection to the external service is lost")
        try:
            self.connection.reconnect()
            # Non-critical: Lost connection but it was able to reconnect
            print("Successfully reconnected to the external service")
        except Exception as e:
            # Critical: failed to reconnect to the external service
            raise RuntimeError(f"Failed to reconnect to the external service: {e}")
    
    return HealthResponse(status="ok")
```
