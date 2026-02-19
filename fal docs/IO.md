> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fal.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Handle Inputs and Outputs

> fal Applications are fully compatible with Pydantic. Any features of Pydantic used in fal endpoint arguments will also work, and you may use Pydantic features for data validation in your endpoint.

Although, in order for your inputs and outputs to be nicely rendered in the playground, you need to use certain conventions that tell our frontend how to interpret the data.

## FalBaseModel

For the best experience defining inputs and outputs, use `FalBaseModel` from the fal SDK. It extends Pydantic's `BaseModel` with features specifically designed for fal applications:

* **Field ordering** - Control the order fields appear in the playground and API schema
* **Hidden fields** - Mark parameters as API-only, hiding them from the playground and API schema.

```python  theme={null}
from fal.toolkit import FalBaseModel, Field, Hidden

class TextToImageInput(FalBaseModel):
    FIELD_ORDERS = ["prompt", "negative_prompt", "image_size"]

    prompt: str = Field(description="Text description of the image")
    negative_prompt: str = Field(default="", description="What to avoid")
    image_size: str = Field(default="1024x1024", description="Output dimensions")

    # Hidden from playground UI but accessible via API
    debug_mode: bool = Hidden(Field(default=False))
    internal_seed: int = Hidden(Field(default=-1))
```

### Field ordering

Use the `FIELD_ORDERS` class variable to control the order fields appear in the API schema and playground. Fields listed in `FIELD_ORDERS` appear first, in the specified order, followed by any remaining fields.

This is particularly useful when you have a base model with common fields that multiple models inherit from. By default, Pydantic places child class fields before parent class fields in the schema. `FIELD_ORDERS` lets you ensure base model fields (like `prompt`) appear first for a consistent user experience.

```python  theme={null}
from fal.toolkit import FalBaseModel, Field, ImageField

# Base model with common fields
class BaseTextInput(FalBaseModel):
    FIELD_ORDERS = ["prompt", "negative_prompt"]

    prompt: str = Field(description="Text prompt")
    negative_prompt: str = Field(default="", description="What to avoid")

# Extended model for image-to-image
class ImageToImageInput(BaseTextInput):
    # Override FIELD_ORDERS to control the full order
    FIELD_ORDERS = ["prompt", "negative_prompt", "image_url", "strength"]

    image_url: str = ImageField(description="Input image")
    strength: float = Field(default=0.8, description="How much to transform")

# Without FIELD_ORDERS, schema would show: image_url, strength, prompt, negative_prompt
# With FIELD_ORDERS, schema shows: prompt, negative_prompt, image_url, strength
```

### Hidden fields

Use `Hidden()` to wrap any field that should be available via API but hidden from the playground UI. This is useful for:

* Testing parameters you want to expose to select API integrations
* Internal debugging flags
* Advanced options that would clutter the UI

<Warning>
  Hidden fields must have a default value or `default_factory` since they cannot be required inputs in the UI.
</Warning>

```python  theme={null}
from fal.toolkit import FalBaseModel, Field, Hidden

class MyInput(FalBaseModel):
    prompt: str = Field(description="User prompt")

    # These won't appear in the playground
    enable_profiling: bool = Hidden(Field(default=False))
    custom_config: dict = Hidden(Field(default_factory=dict))
```

### Media field helpers

For better playground rendering, use the specialized field helpers instead of plain `Field()`:

| Helper            | UI Rendering         |
| ----------------- | -------------------- |
| `FileField(...)`  | Generic file upload  |
| `ImageField(...)` | Image upload/preview |
| `AudioField(...)` | Audio upload/player  |
| `VideoField(...)` | Video upload/player  |

```python  theme={null}
from fal.toolkit import FalBaseModel, ImageField, AudioField

class MyInput(FalBaseModel):
    # Renders as image upload in playground
    input_image: str = ImageField(description="Source image")

    # Renders as audio upload in playground
    voice_sample: str = AudioField(description="Voice sample for cloning")
```

These helpers work with both Pydantic v1 and v2. See the [Standard Inputs and Outputs](#standard-inputs-and-outputs) section below for more details on each media type, including naming conventions and output handling.

## Standard Inputs and Outputs

### File Input

Name your field with a `file_url` suffix and it will be rendered as a file in the playground, allowing users to upload or download the file.

```python  theme={null}
from pydantic import BaseModel

class MyInput(BaseModel):
    file_url: str

class MyOutput(BaseModel):
    ...

class MyApp(fal.App):
    @fal.endpoint("/")
    def predict(self, input: MyInput) -> MyOutput:
        input_path = download_file(input.file_url)
        ...
        return MyOutput(...)
```

Alternatively if that naming convention is not suitable, you can use the `FileField` helper:

```python  theme={null}
from fal.toolkit import FalBaseModel, FileField

class MyInput(FalBaseModel):
    document: str = FileField(description="Upload a document")
```

<Accordion title="Manual approach with json_schema_extra">
  For advanced use cases, you can manually specify the `ui` metadata. The syntax differs between Pydantic versions:

  <CodeGroup>
    ```python Pydantic v2 theme={null}
    from pydantic import BaseModel, Field

    class MyInput(BaseModel):
        document: str = Field(..., json_schema_extra={"ui": {"field": "file"}})
    ```

    ```python Pydantic v1 theme={null}
    from pydantic import BaseModel, Field

    class MyInput(BaseModel):
        document: str = Field(..., ui={"field": "file"})
    ```
  </CodeGroup>
</Accordion>

### File Output

```python  theme={null}
from fal.toolkit import File, download_file
from pydantic import BaseModel

class MyInput(BaseModel):
    ...

class MyOutput(BaseModel):
    file: File


class MyApp(fal.App):
    @fal.endpoint("/")
    def predict(self, input: MyInput) -> MyOutput:
        ...
        return MyOutput(file=File.from_path(output_path))
```

Using `File` class for your output will include additional metadata about the file:

```json  theme={null}
{
  "file": {
    "url": "https://example.com/file.bin",
    "content_type": "application/octet-stream",
    "file_name": "file.bin",
    "file_size": 1024,
  }
}
```

### Image Input

Name your field with a `image_url` suffix and it will be rendered as an image in the playground, allowing users to upload or download the image.

```python  theme={null}
from pydantic import BaseModel
from fal.toolkit import download_file

class MyInput(BaseModel):
    image_url: str

class MyOutput(BaseModel):
    ...

class MyApp(fal.App):
    @fal.endpoint("/")
    def predict(self, input: MyInput) -> MyOutput:
        input_path = download_file(input.image_url)
        ...
        return MyOutput(...)
```

Alternatively if that naming convention is not suitable, you can use the `ImageField` helper:

```python  theme={null}
from fal.toolkit import FalBaseModel, ImageField

class MyInput(FalBaseModel):
    photo: str = ImageField(description="Upload a photo")
```

<Accordion title="Manual approach with json_schema_extra">
  For advanced use cases, you can manually specify the `ui` metadata. The syntax differs between Pydantic versions:

  <CodeGroup>
    ```python Pydantic v2 theme={null}
    from pydantic import BaseModel, Field

    class MyInput(BaseModel):
        photo: str = Field(..., json_schema_extra={"ui": {"field": "image"}})
    ```

    ```python Pydantic v1 theme={null}
    from pydantic import BaseModel, Field

    class MyInput(BaseModel):
        photo: str = Field(..., ui={"field": "image"})
    ```
  </CodeGroup>
</Accordion>

### Image Output

```python  theme={null}
from fal.toolkit import Image
from pydantic import BaseModel

class MyInput(BaseModel):
    ...

class MyOutput(BaseModel):
    image: Image


class MyApp(fal.App):
    @fal.endpoint("/")
    def predict(self, input: MyInput) -> MyOutput:
        ...
        return MyOutput(image=Image.from_path(output_path))
```

Using `Image` class for your output will include additional metadata about the image:

```json  theme={null}
{
  "image": {
    "url": "https://example.com/image.png",
    "content_type": "image/png",
    "file_name": "image.png",
    "file_size": 1024,
    "width": 1024,
    "height": 1024,
  }
}
```

### Image Dataset Input

Use `image_urls` suffix to render a dataset of images in the playground.

```python  theme={null}
from typing import List
from pydantic import BaseModel

class MyInput(BaseModel):
    image_urls: List[str]
```

### Audio Input

Name your field with a `audio_url` suffix and it will be rendered as an audio in the playground, allowing users to upload or download the audio.

```python  theme={null}
from typing import List
from pydantic import BaseModel

class MyInput(BaseModel):
    audio_url: str

class MyOutput(BaseModel):
    ...

class MyApp(fal.App):
    @fal.endpoint("/")
    def predict(self, input: MyInput) -> MyOutput:
        input_path = download_file(input.audio_url)
        ...
        return MyOutput(...)
```

Alternatively if that naming convention is not suitable, you can use the `AudioField` helper:

```python  theme={null}
from fal.toolkit import FalBaseModel, AudioField

class MyInput(FalBaseModel):
    voice_sample: str = AudioField(description="Upload a voice sample")
```

<Accordion title="Manual approach with json_schema_extra">
  For advanced use cases, you can manually specify the `ui` metadata. The syntax differs between Pydantic versions:

  <CodeGroup>
    ```python Pydantic v2 theme={null}
    from pydantic import BaseModel, Field

    class MyInput(BaseModel):
        voice_sample: str = Field(..., json_schema_extra={"ui": {"field": "audio"}})
    ```

    ```python Pydantic v1 theme={null}
    from pydantic import BaseModel, Field

    class MyInput(BaseModel):
        voice_sample: str = Field(..., ui={"field": "audio"})
    ```
  </CodeGroup>
</Accordion>

### Audio Output

```python  theme={null}
from fal.toolkit import Audio
from pydantic import BaseModel

class MyInput(BaseModel):
    ...

class MyOutput(BaseModel):
    audio: Audio


class MyApp(fal.App):
    @fal.endpoint("/")
    def predict(self, input: MyInput) -> MyOutput:
        ...
        return MyOutput(audio=Audio.from_path(output_path))
```

Using `Audio` class for your output will include additional metadata about the audio:

```json  theme={null}
{
  "audio": {
    "url": "https://example.com/audio.mp3",
    "content_type": "audio/mpeg",
    "file_name": "audio.mp3",
    "file_size": 1024,
  }
}
```

### Audio Dataset Input

Use `audio_urls` suffix to render a dataset of audios in the playground.

```python  theme={null}
from typing import List
from pydantic import BaseModel

class MyInput(BaseModel):
    audio_urls: List[str]
```

### Video Input

Name your field with a `video_url` suffix and it will be rendered as a video in the playground, allowing users to upload or download the video.

```python  theme={null}
from typing import List
from pydantic import BaseModel

class MyInput(BaseModel):
    video_url: str

class MyOutput(BaseModel):
    ...

class MyApp(fal.App):
    @fal.endpoint("/")
    def predict(self, input: MyInput) -> MyOutput:
        input_path = download_file(input.video_url)
        ...
        return MyOutput(...)
```

Alternatively if that naming convention is not suitable, you can use the `VideoField` helper:

```python  theme={null}
from fal.toolkit import FalBaseModel, VideoField

class MyInput(FalBaseModel):
    clip: str = VideoField(description="Upload a video clip")
```

<Accordion title="Manual approach with json_schema_extra">
  For advanced use cases, you can manually specify the `ui` metadata. The syntax differs between Pydantic versions:

  <CodeGroup>
    ```python Pydantic v2 theme={null}
    from pydantic import BaseModel, Field

    class MyInput(BaseModel):
        clip: str = Field(..., json_schema_extra={"ui": {"field": "video"}})
    ```

    ```python Pydantic v1 theme={null}
    from pydantic import BaseModel, Field

    class MyInput(BaseModel):
        clip: str = Field(..., ui={"field": "video"})
    ```
  </CodeGroup>
</Accordion>

### Video Output

```python  theme={null}
from fal.toolkit import Video
from pydantic import BaseModel

class MyInput(BaseModel):
    ...

class MyOutput(BaseModel):
    video: Video


class MyApp(fal.App):
    @fal.endpoint("/")
    def predict(self, input: MyInput) -> MyOutput:
        ...
        return MyOutput(video=Video.from_path(output_path))
```

Using `Video` class for your output will include additional metadata about the video:

```json  theme={null}
{
  "video": {
    "url": "https://example.com/video.mp4",
    "content_type": "video/mp4",
    "file_name": "video.mp4",
    "file_size": 1024,
  }
}
```

### Video Dataset Input

Use `video_urls` suffix to render a dataset of videos in the playground.

```python  theme={null}
from typing import List
from pydantic import BaseModel

class MyInput(BaseModel):
    video_urls: List[str]
```
