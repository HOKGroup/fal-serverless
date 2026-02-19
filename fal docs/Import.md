> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fal.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Import Code

> When building serverless applications with fal, you may need to import and use custom Python modules, third-party packages, or code from external repositories. This is common when you want to:

* **Reuse existing code**: Leverage your existing Python modules and libraries
* **Organize your codebase**: Split your application logic into multiple files for better maintainability
* **Use external dependencies**: Integrate with third-party packages or libraries not included in the base environment
* **Share code across projects**: Import common utilities or models from shared repositories

fal provides several ways to handle Python module imports depending on your use case, from simple local modules to complex external repositories with specific dependencies.

## Requirements

```python  theme={null}
class MyApp(fal.App):
    requirements = ["mymodule"]

    @fal.endpoint("/")
    def predict(self, input: MyInput) -> MyOutput:
        myfunction(input)
        ...
```

## App Files

The `app_files` attribute allows you to include local files and directories from your local machine in your fal application, making them available in the serverless environment exactly as they appear locally.

Use this to bring your local code, configs, weights, or any other files from your local filesystem to the fal serverless environment. Files and imports work the same way they do on your local machine.

### Basic Usage

Add files or directories to your application by listing their local paths in the `app_files` attribute:

```python  theme={null}
class MyApp(fal.App):
    app_files = [
        "utils/helper.py",     # Include a single file
        "models",              # Include entire directory
        "checkpoint.pt",       # Include a weights file
    ]

    @fal.endpoint("/")
    def predict(self, input: MyInput) -> MyOutput:
        # Import modules just like you would locally
        from utils.helper import process_data
        from models.classifier import MyModel
        
        result = process_data(input)
        # Access files using relative paths, just like locally
        model = MyModel.load_checkpoint("checkpoint.pt")
        return model.predict(result)
```

### How App Files Work

When you include files in `app_files`, they are transferred to the serverless environment and made available relative to your fal app file location, **exactly as they exist on your local machine**.

**Key Points:**

* Files maintain their relative structure to your app file
* Imports work naturally - no special prefixes needed
* File paths work with standard relative paths (`./`, `../`)
* The serverless environment mirrors your local file layout

**Example:**

If locally you have:

```
project/
├── my_fal_app.py
├── utils/
│   └── helper.py
└── models/
    └── classifier.py
```

Then in your serverless function:

```python  theme={null}
from utils.helper import process_data    # Works naturally
from models.classifier import MyModel    # Just like local
```

### Setting the Context Directory

By default, all file paths are resolved relative to the directory containing your fal app file. You can customize this base directory using the `app_files_context_dir` attribute:

```python  theme={null}
# Project structure:
# files/
# ├── weights/
# │   └── checkpoint.pt
# ├── utils/
# │   └── loader.py
# ├── src/
# │   └── my_fal_app.py
# │   ├── data_processing/
# │   │   ├── __init__.py
# │   │   └── preprocessor.py
# │   └── models/
# │       ├── __init__.py
# │       └── neural_net.py

class MyApp(fal.App):
    # Set context to the `files` directory (parent of src/)
    app_files_context_dir = "../"
    
    app_files = [
        "src/data_processing",
        "src/models",
        "weights",
        "utils",
    ]
    
    requirements = ["torch", "numpy"]

    @fal.endpoint("/predict")
    def predict(self, input: MyInput) -> MyOutput:
        # Import modules relative to your app file location
        from data_processing.preprocessor import clean_data
        from models.neural_net import NeuralNetwork
        from utils.loader import load
        
        # Access files with relative paths, just like locally
        cleaned_input = clean_data(input.raw_data)
        model = NeuralNetwork()
        load(model, "../weights/checkpoint.pt")
        prediction = model.forward(cleaned_input)
        
        return MyOutput(result=prediction)
```

**Path Security:**

* Absolute paths are **not allowed** and will be rejected
* All paths must be within the context directory
* Paths attempting to escape the context directory (e.g., `../../outside`) will be rejected. To access these, set `app_files_context_dir` to a higher directory.
* All included files are read-only in the serverless environment
* Files are included on a per-app basis - files uploaded for one app will not be available in another app unless specified in its `app_files`

### Ignoring Files

Use `app_files_ignore` to exclude unwanted files using regex patterns:

```python  theme={null}
class MyApp(fal.App):
    app_files = ["my_project/"]
    app_files_ignore = [
        r"\.pyc$",          # Python bytecode
        r"__pycache__/",    # Python cache directories
        r"\.git/",          # Git directories
        r"\.env$",          # Environment files
        r"test_.*\.py$",    # Test files
    ]
```

**Default ignored patterns:**

```python  theme={null}
DEFAULT_APP_FILES_IGNORE = [
    r"\.pyc$",
    r"__pycache__/",
    r"\.git/",
    r"\.DS_Store$",
]
```

#### Best Practices

* **Keep it organized**: Use meaningful directory names and structure
* **Minimize deployment size**: Only include the files you actually need
* **Use `app_files_context_dir`**: Set a common base directory for multi-app projects
* **Use relative paths**: Better portability across different environments
* **Ignore unnecessary files**: Use `app_files_ignore` to exclude development and testing files
* **Never use absolute paths**: They will be rejected
* **Think local-first**: Your serverless environment will mirror your local file structure

## Local Python Modules

You can import local Python modules by adding them to the `local_python_modules` attribute of your fal application.

```python  theme={null}
from mymodule import myfunction

class MyApp(fal.App):
    local_python_modules = ["mymodule"]

    @fal.endpoint("/")
    def predict(self, input: MyInput) -> MyOutput:
        myfunction(input)
        ...
```

## Git Repositories

You can clone Git repositories directly into your fal application using the `clone_repository` function.

This is particularly useful for incorporating external libraries, model implementations, or shared code from Git repositories.

```python  theme={null}
from fal.toolkit import clone_repository


class MyApp(fal.App):
    def setup(self):
        path = clone_repository(
            "https://github.com/myorg/myrepo",
            commit_hash="1418c53bcfaf4efc1034207dcb39d093d5fff645",
            # Add repository path to PYTHONPATH to allow importing modules
            include_to_path=True,
        )

        import myproject
        ...
```
