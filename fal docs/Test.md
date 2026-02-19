> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fal.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Test Models and Endpoints

> Automated testing helps you catch bugs early, validate your model's behavior with different inputs, and ensure your endpoints work as expected. This can be particularly useful when implementing continuous integration pipelines or when debugging model performance issues.

## Testing Models with AppClient

The `AppClient` provides a convenient way to test your models and endpoints programmatically. When you use `AppClient`, it automatically deploys your app to fal's serverless infrastructure in ephemeral mode, runs your tests against the live endpoints, and then cleans up the deployment when testing is complete.

Let's start with a sample image generation app that we want to test:

Given the following app:

```python  theme={null}
import fal
from pydantic import BaseModel, Field
from fal.toolkit import Image

class ImageModelInput(BaseModel): # ...

class MyApp(fal.App):  # ...
    keep_alive = 300

    def setup(self): # ...

    @fal.endpoint("/")
    def generate_image(self, request: ImageModelInput) -> Image: # ...
```

Now you can write comprehensive tests for this app:

```python  theme={null}
def test_myapp():
    with fal.app.AppClient.connect(MyApp) as client:
        result = client.generate_image(prompt="A cat holding a sign that says hello world")
        assert result is not None
        assert hasattr(result, 'url')
```
