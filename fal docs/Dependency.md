> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fal.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Manage Dependencies

> Install pip packages, prebuilt wheels, and private packages in your fal applications.

The `requirements` class variable in your fal App specifies which Python packages to install. It supports standard pip syntax, including version specifiers, wheel URLs, and private package indexes.

## Basic Requirements

Specify packages with version pinning for reproducible builds:

```python  theme={null}
class MyApp(fal.App):
    requirements = [
        "torch==2.5.0",
        "transformers==4.51.3",
        "diffusers==0.31.0",
        "accelerate==1.6.0",
    ]
```

<Note>
  Always pin your package versions to ensure reproducible builds across deployments.
</Note>

## Using Prebuilt Wheels

You can install packages directly from wheel URLs. This is useful for custom-built packages or packages not available on PyPI.

### Direct URL

Provide the full URL to a wheel file:

```python  theme={null}
requirements = [
    "https://your-storage.example.com/wheels/mypackage-1.0.0-cp311-cp311-linux_x86_64.whl",
]
```

### Package @ URL (PEP 440)

Use the `package@url` syntax to give the package a name for dependency resolution:

```python  theme={null}
requirements = [
    "mypackage@https://your-storage.example.com/wheels/mypackage-1.0.0-cp311-cp311-linux_x86_64.whl",
]
```

This syntax is recommended when other packages depend on `mypackage`, as pip can properly track the dependency.

## Alternative Package Indexes

Use `--extra-index-url` or `--find-links` to install packages from alternative sources.

### Extra Index URL

Install packages from an additional PyPI-compatible index:

```python  theme={null}
requirements = [
    "torch==2.5.0",
    "--extra-index-url",
    "https://download.pytorch.org/whl/cu124",
]
```

<Warning>
  The `--extra-index-url` flag must appear **before** any packages that need it. Place index flags at the beginning or directly before the relevant packages.
</Warning>

### Find Links

Use `--find-links` to search for packages in a directory or URL containing wheel files:

```python  theme={null}
requirements = [
    "mypackage",
    "--find-links",
    "https://github.com/your-org/releases/download/v1.0.0/",
]
```

### Multiple Indexes

Combine multiple index sources when needed:

```python  theme={null}
requirements = [
    "--extra-index-url",
    "https://download.pytorch.org/whl/cu124",
    "--extra-index-url",
    "https://your-company.example.com/simple",
    "torch==2.5.0",
    "your-internal-package==1.0.0",
]
```

## Private Packages

### Private Git Repositories

Install directly from a private GitHub repository using a personal access token:

```python  theme={null}
requirements = [
    "git+https://YOUR_TOKEN@github.com/your-org/private-repo.git",
]
```

Pin to a specific commit or tag for reproducibility:

```python  theme={null}
requirements = [
    "git+https://YOUR_TOKEN@github.com/your-org/private-repo.git@v1.0.0",
    "git+https://YOUR_TOKEN@github.com/your-org/private-repo.git@abc123def",
]
```

<Warning>
  **Security Consideration**: Tokens embedded in requirements are visible in your code. For better security:

  * Use short-lived tokens when possible
  * Consider hosting wheels on a storage service with pre-signed URLs
  * Use [fal secrets](/serverless/deployment-operations/manage-secrets-securely) for sensitive values in your app code
</Warning>

### Private PyPI Index

Install from a private PyPI server with authentication:

```python  theme={null}
requirements = [
    "--extra-index-url",
    "https://username:password@pypi.your-company.com/simple",
    "your-private-package==1.0.0",
]
```

### Pre-signed URLs

For private storage (S3, GCS, etc.), generate a pre-signed URL with an expiration time:

```python  theme={null}
requirements = [
    "https://your-bucket.s3.amazonaws.com/wheels/mypackage-1.0.0.whl?AWSAccessKeyId=...&Signature=...&Expires=...",
]
```

## Dynamic Wheel Selection

When you need different wheels for different Python versions or platforms, use a helper function:

```python  theme={null}
def get_package_wheel():
    import sys
    wheels = {
        10: "https://example.com/wheels/mypackage-1.0.0-cp310-cp310-linux_x86_64.whl",
        11: "https://example.com/wheels/mypackage-1.0.0-cp311-cp311-linux_x86_64.whl",
    }
    return wheels[sys.version_info.minor]


class MyApp(fal.App):
    machine_type = "GPU"
    requirements = [
        "torch==2.5.0",
        get_package_wheel(),
    ]
```

<Note>
  Helper functions are evaluated at deploy time on your local machine, so they have access to local environment variables and can make decisions based on the target Python version.
</Note>
